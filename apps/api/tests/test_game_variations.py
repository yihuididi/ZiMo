"""Unified Bao, scoring, settlement and physical Kong-4 regression matrix.

Uses unittest so the same assertions run in CPython and the Worker dependency environment.
"""
from __future__ import annotations

import unittest

from app.game import (
    GameConfig, SeatId, TileFamily as F, Wind, WinSource, ClaimKind, MeldKind,
    MeldState, DiscardState, HandState, HandId, PlayerHand, PhysicalTile, TileId,
    TileFace, WallState, DeclareWin, Kong, KongRobberyPhase, Discard, Pass,
    SingaporeGameEngine, validate_room, serialize_room_state, deserialize_room_state,
    PendingDeadline, build_seat_observation,
)
from app.game.bao import qualifying_liability, record_liability, fresh_discard
from app.game.model import BaoLiability, PayerAmount, Settlement
from app.game.payments import settle_win, award_immediate
from app.game.scoring import evaluate_win, WinEvaluation, WONDERS
from app.game.model import FanAward
from test_game_setup import IdentityRandomSource, preview_room
from test_game_claims import started
from test_game_scoring import player, face

S = tuple(SeatId(f"seat-{i}") for i in range(4))


def scoring(values, config=GameConfig(), source=WinSource.SELF_DRAW, bonuses=None):
    p = player(values, bonuses)
    hand = HandState(hand_id=HandId("scoring"), player_hands=(p, *(PlayerHand(seat_id=s) for s in S[1:])),
                     wall=WallState(live_tiles=(PhysicalTile(tile_id=TileId("wall"), face=face(F.DOTS, 8)),)))
    return evaluate_win(hand, p, winning_tile=None, source=source, prevailing_wind=Wind.EAST,
                        own_wind=Wind.EAST, config=config)


class VariationScoringTests(unittest.TestCase):
    def test_pairs_quads_composition_and_disabled(self):
        values = [face(F.BAMBOO, n) for n in (1,1,1,1,3,3,5,5,7,7,9,9)] + [face(F.DOTS, 2)]*2
        self.assertIsNone(scoring(values))
        result = scoring(values, GameConfig(seven_pairs_enabled=True))
        self.assertEqual((result.pattern, result.fan), ("SEVEN_PAIRS", 3))
        self.assertIsNone(scoring(values, GameConfig(seven_pairs_enabled=True, minimum_fan=4)))
        pure = [face(F.BAMBOO, n) for n in (1,1,1,1,2,2,4,4,6,6,8,8,9,9)]
        result = scoring(pure, GameConfig(seven_pairs_enabled=True, concealed_self_draw_bonus_enabled=True), bonuses=[face(F.ANIMAL, "CAT")])
        self.assertEqual(result.fan, 9)
        self.assertEqual({a.name for a in result.awards}, {"Seven Pairs", "Full Color", "Concealed Self-draw", "Animal Cat"})

    def test_standard_decomposition_can_beat_pairs(self):
        values = [face(F.BAMBOO, n) for n in (1,1,2,2,3,3,4,4,5,5,6,6,7,7)]
        result = scoring(values, GameConfig(seven_pairs_enabled=True))
        self.assertEqual((result.pattern, result.fan), ("STANDARD", 8))

    def test_automatic_honors_toggle_and_legacy_scoring(self):
        for family, values, setting in ((F.DRAGON, ("RED","GREEN","WHITE"), "automatic_dragon_wins_enabled"),
                                         (F.WIND, ("EAST","SOUTH","WEST","NORTH"), "automatic_wind_wins_enabled")):
            with self.subTest(setting=setting):
                tiles = [face(family,v) for v in values for _ in range(3)]
                incomplete = tiles + [face(F.BAMBOO,n) for n in range(1, 15-len(tiles))]
                self.assertIsNotNone(scoring(incomplete))
                disabled = GameConfig(**{setting: False})
                self.assertIsNone(scoring(incomplete, disabled))
                complete = tiles + ([face(F.DOTS,n) for n in (1,2,3,5,5)] if family is F.DRAGON else [face(F.DOTS,5)]*2)
                result = scoring(complete, disabled)
                self.assertEqual(result.pattern, "STANDARD")
                self.assertIn("Big Dragons" if family is F.DRAGON else "Big Winds", {a.name for a in result.awards})

    def test_concealed_bonus_can_meet_minimum_only_on_self_draw(self):
        chicken = [face(F.BAMBOO,n) for n in (1,2,3,4,5,6)] + [face(F.DOTS,n) for n in (1,2,3,4,5,6)] + [face(F.DRAGON,"RED")]*2
        config = GameConfig(concealed_self_draw_bonus_enabled=True)
        self.assertIsNone(scoring(chicken))
        self.assertEqual(scoring(chicken, config).fan, 1)
        self.assertIsNone(scoring(chicken, config, WinSource.DISCARD))


class BaoTests(unittest.TestCase):
    def setUp(self):
        _, self.room = started(IdentityRandomSource())
        self.serial = 0

    def tile(self, family, value):
        self.serial += 1
        return PhysicalTile(tile_id=TileId(f"bao-{self.serial}"), face=face(family,value))

    def evidence(self, sets, discarded, *, remaining=20, concealed=(), bonuses=()):
        melds = tuple(MeldState(kind=MeldKind.PONG, tiles=tuple(self.tile(*v) for _ in range(3))) for v in sets)
        p = self.room.match.current_hand.player_hands[1].model_copy(update={
            "melds": melds, "concealed_tiles": tuple(self.tile(*v) for v in concealed),
            "drawn_tile": None, "bonus_tiles": tuple(self.tile(*v) for v in bonuses)})
        h = self.room.match.current_hand.model_copy(update={"player_hands": (self.room.match.current_hand.player_hands[0], p, *self.room.match.current_hand.player_hands[2:]),
            "discards": (DiscardState(sequence=1, tile=self.tile(*discarded), discarded_by_seat_id=S[0], live_tiles_remaining=remaining),)})
        return h

    def test_honor_triggers_and_near_misses(self):
        for family, exposed, missing, reason in ((F.DRAGON,("RED","GREEN"),"WHITE","DRAGONS"),
                                                  (F.WIND,("EAST","WEST","NORTH"),"SOUTH","WINDS")):
            for kind in (ClaimKind.PONG, ClaimKind.KONG):
                with self.subTest(family=family, kind=kind):
                    h = self.evidence([(family,v) for v in exposed], (family,missing))
                    b = qualifying_liability(self.room,h,S[1],kind)
                    self.assertIn(reason,b.reasons)
                    self.assertIsNone(qualifying_liability(self.room,h,S[1],ClaimKind.CHOW))
                    short = self.evidence([(family,v) for v in exposed[:-1]],(family,missing))
                    self.assertIsNone(qualifying_liability(self.room,short,S[1],kind))

    def test_visible_fan_uses_public_bonuses_and_double_value_wind(self):
        # Beneficiary seat 1 is South; move dealer there so East is worth two fan.
        self.room = self.room.model_copy(update={"match": self.room.match.model_copy(update={"dealer_seat_id": S[1]})})
        h = self.evidence([(F.DRAGON,"RED")], (F.WIND,"EAST"), bonuses=((F.ANIMAL,"CAT"),(F.ANIMAL,"MOUSE")))
        b = qualifying_liability(self.room,h,S[1],ClaimKind.PONG)
        self.assertEqual(b.reasons,("VISIBLE_FAN_LIMIT",))
        hidden = self.evidence([], (F.WIND,"EAST"), concealed=((F.DRAGON,"RED"),)*3)
        self.assertIsNone(qualifying_liability(self.room,hidden,S[1],ClaimKind.PONG))

    def test_freshness_threshold_and_claimed_history(self):
        for remaining, expected in ((3,True),(4,False),(5,False)):
            h = self.evidence([], (F.DOTS,6),remaining=remaining)
            self.assertEqual(qualifying_liability(self.room,h,S[1],ClaimKind.WIN) is not None,expected)
        old = h.discards[0].model_copy(update={"claimed_by_seat_id":S[2],"claim_kind":ClaimKind.PONG})
        new = h.discards[0].model_copy(update={"sequence":2,"live_tiles_remaining":3})
        h = h.model_copy(update={"discards":(old,new)})
        self.assertFalse(fresh_discard(h,2))
        self.assertIsNone(qualifying_liability(self.room,h,S[1],ClaimKind.WIN))

    def test_full_color_and_multiple_reasons(self):
        result = WinEvaluation(4,(FanAward(name="Full Color",fan=4),),"STANDARD")
        h = self.evidence([(F.DOTS,n) for n in (1,2,3)],(F.DOTS,4),remaining=3)
        b = qualifying_liability(self.room,h,S[1],ClaimKind.WIN,result)
        self.assertEqual(b.reasons,("FULL_COLOR","FRESH_DISCARD"))
        self.assertIsNone(qualifying_liability(self.room,h,S[1],ClaimKind.PONG))
        for family,value in ((F.BAMBOO,4),(F.DRAGON,"RED")):
            other = h.model_copy(update={"discards":(h.discards[0].model_copy(update={"tile":self.tile(family,value),"live_tiles_remaining":20}),)})
            self.assertIsNone(qualifying_liability(self.room,other,S[1],ClaimKind.WIN,result))

    def test_latest_feeder_replaces_and_new_hand_resets(self):
        h = self.evidence([(F.DRAGON,"RED"),(F.DRAGON,"GREEN")],(F.DRAGON,"WHITE"))
        first = qualifying_liability(self.room,h,S[1],ClaimKind.PONG)
        h = record_liability(h, first)
        later = first.model_copy(update={"feeder_seat_id":S[2],"reasons":("VISIBLE_FAN_LIMIT",),"discard_sequence":2})
        h = record_liability(h,later)
        self.assertEqual(h.bao_liabilities,(later,))
        self.assertEqual(HandState(hand_id=HandId("new-hand"),player_hands=tuple(PlayerHand(seat_id=s) for s in S)).bao_liabilities,())

    def test_settlement_redirects_once_and_only_for_applicable_feeder(self):
        for shooter in (False,True):
            room = self.room.model_copy(update={"config":GameConfig(shooter_mode=shooter,extra_self_draw_points=3)})
            h = room.match.current_hand.model_copy(update={"bao_liabilities":(BaoLiability(beneficiary_seat_id=S[1],feeder_seat_id=S[0],reasons=("DRAGONS","VISIBLE_FAN_LIMIT"),discard_sequence=1),)})
            for source,provider,expected in ((WinSource.SELF_DRAW,None,{S[0]:57}),
                    (WinSource.DISCARD,S[0],{S[0]:32}),
                    (WinSource.DISCARD,S[2],{S[2]:32} if shooter else {S[0]:8,S[2]:16,S[3]:8})):
                with self.subTest(shooter=shooter,source=source,provider=provider):
                    m,paid,_ = settle_win(room,room.match,h,winner=S[1],provider=provider,source=source,pattern="STANDARD",capped_fan=3)
                    self.assertEqual({p.seat_id:p.amount for p in paid.settlement.final},expected)
                    self.assertEqual(sum(b.points for b in m.balances),0)
                    self.assertEqual(sum(p.amount for p in paid.settlement.baseline),sum(expected.values()))

    def test_current_discard_replaces_earlier_feeder_before_settlement(self):
        h = self.evidence([], (F.DOTS,6),remaining=3)
        old = BaoLiability(beneficiary_seat_id=S[1],feeder_seat_id=S[2],reasons=("DRAGONS",),discard_sequence=1)
        h = record_liability(record_liability(h,old),qualifying_liability(self.room,h,S[1],ClaimKind.WIN))
        _, paid,_ = settle_win(self.room,self.room.match,h,winner=S[1],provider=S[0],source=WinSource.DISCARD,pattern="STANDARD",capped_fan=2)
        self.assertEqual(paid.settlement.final,(PayerAmount(seat_id=S[0],amount=16),))
        self.assertEqual(paid.settlement.liability.reasons,("FRESH_DISCARD",))

    def test_fresh_kong_payment_threshold_shooter_and_no_persistent_bao(self):
        for enabled in (False,True):
            for shooter in (False,True):
                for remaining in (6,7):
                    with self.subTest(enabled=enabled,shooter=shooter,remaining=remaining):
                        room = self.room.model_copy(update={"config":GameConfig(fresh_kong_pay_all_enabled=enabled,shooter_mode=shooter)})
                        h = self.evidence([], (F.DOTS,6),remaining=remaining)
                        d = h.discards[0]
                        meld = MeldState(kind=MeldKind.KONG,kong_kind="KONG_3",tiles=(d.tile,*(self.tile(F.DOTS,6) for _ in range(3))),claimed_from_seat_id=S[0],discard_sequence=1)
                        p = h.player_hands[1].model_copy(update={"melds":(meld,),"bonus_tiles":()})
                        h = h.model_copy(update={"player_hands":tuple(p if x.seat_id==S[1] else x.model_copy(update={"bonus_tiles":()}) for x in h.player_hands),"payments":()})
                        m,paid = award_immediate(room,room.match,h)
                        self.assertEqual(len(paid.payments),1 if shooter or (enabled and remaining<7) else 3)
                        self.assertEqual(sum(x.amount for x in paid.payments),6)
                        self.assertEqual(paid.bao_liabilities,())
                        self.assertEqual(award_immediate(room,m,paid)[1].payments,paid.payments)


class WondersDeck(IdentityRandomSource):
    def shuffled(self,values):
        pool=list(values)
        def take(f,v):
            t=next(t for t in pool if t.face.family is f and t.face.value==v)
            pool.remove(t)
            return t
        hands={0:[take(F.BAMBOO,1) for _ in range(3)]+[take(F.DOTS,n) for n in (2,2,3,3,4,4,5,5,6,6)],
               1:[take(f,v) for f,v in sorted(WONDERS,key=lambda x:(x[0].value,str(x[1]))) if (f,v)!=(F.BAMBOO,1)]+[take(F.WIND,"EAST")]}
        draw=take(F.BAMBOO,1)
        for seat in (2,3):
            hands[seat]=[]
            for _ in range(13):
                t=next(t for t in pool if t.face.family in {F.DOTS,F.CHARACTERS,F.BAMBOO})
                pool.remove(t); hands[seat].append(t)
        return tuple(hands[seat][i] for i in range(13) for seat in range(4))+(draw,*pool)


def kong_four_room(config=GameConfig(kong_four_robbery_enabled=True)):
    engine=SingaporeGameEngine(WondersDeck())
    state=engine.setup_match(preview_room(human_at_zero=True).model_copy(update={"config":config})).state
    return engine,state


class KongFourTests(unittest.TestCase):
    def open(self,config=GameConfig(kong_four_robbery_enabled=True)):
        engine,state=kong_four_room(config)
        kong=next(a for a in engine.legal_actions(state,S[0]) if isinstance(a,Kong))
        return engine,state,engine.transition(state,kong)

    def test_robbed_and_reconstructed_payments_and_conservation(self):
        for shooter in (False,True):
            engine,before,transition=self.open(GameConfig(kong_four_robbery_enabled=True,shooter_mode=shooter,extra_self_draw_points=10))
            window=transition.state
            self.assertEqual(transition.effects[0].duration_ms,3000)
            self.assertEqual(window.match.current_hand.phase.kong_kind,"KONG_4")
            self.assertEqual(window.match.current_hand.wall,before.match.current_hand.wall)
            window=window.model_copy(update={"revision":window.revision+1,"pending_deadline":PendingDeadline(window_id=window.match.current_hand.phase.window_id,deadline_ms=3000)})
            window=deserialize_room_state(serialize_room_state(window))
            actions=engine.legal_actions(window,S[1])
            self.assertTrue(any(isinstance(a,DeclareWin) for a in actions))
            chosen=engine.transition(window,next(a for a in actions if isinstance(a,DeclareWin))).state
            completed=engine.resolve_discard_window(chosen,chosen.match.current_hand.phase.window_id).state
            h=completed.match.current_hand
            self.assertEqual(h.result.reason,"THIRTEEN_WONDERS")
            self.assertEqual(h.settlement.robbed_kong_kind,"KONG_4")
            self.assertEqual(sum(p.amount for p in h.settlement.final),192)
            self.assertEqual(len(h.settlement.final),1 if shooter else 3)
            self.assertEqual(sum(t.face==face(F.BAMBOO,1) for t in (*h.player_hands[0].concealed_tiles, *((h.player_hands[0].drawn_tile,) if h.player_hands[0].drawn_tile else ()))),3)
            self.assertEqual(h.player_hands[0].melds,())
            self.assertEqual(h.wall,before.match.current_hand.wall)
            validate_room(completed)

    def test_unrobbed_and_disabled(self):
        engine,before,transition=self.open()
        window=transition.state
        passed=engine.transition(window,next(a for a in engine.legal_actions(window,S[1]) if isinstance(a,Pass))).state
        self.assertIsInstance(passed.match.current_hand.phase,KongRobberyPhase)
        result=engine.resolve_discard_window(passed,passed.match.current_hand.phase.window_id).state
        self.assertEqual(result.match.current_hand.player_hands[0].melds[0].kong_kind,"KONG_4")
        self.assertLess(len(result.match.current_hand.wall.live_tiles),len(before.match.current_hand.wall.live_tiles))
        validate_room(result)
        _,_,disabled=self.open(GameConfig())
        self.assertNotIsInstance(disabled.state.match.current_hand.phase,KongRobberyPhase)

    def test_projection_has_no_physical_proposal_ids(self):
        _,_,transition=self.open()
        state=transition.state
        observation=build_seat_observation(state,S[1]).canonical_json()
        for tile_id in state.match.current_hand.phase.proposed_tile_ids:
            self.assertNotIn(str(tile_id),observation)
        self.assertIn('"kongKind":"KONG_4"',observation)


def honor_room(automatic):
    """Two exposed Dragons, with a third fed by the active player."""
    from app.game import AwaitingDiscardPhase
    from app.game.singapore_game import _room_with_hand
    from app.game.tiles import sort_playable_tiles
    engine, state = started(IdentityRandomSource())
    h = state.match.current_hand
    pool = [*h.wall.live_tiles, *h.wall.reserve_tiles,
            *(t for p in h.player_hands for t in (*p.concealed_tiles, *p.bonus_tiles, *((p.drawn_tile,) if p.drawn_tile else ())))]
    def take(f, v):
        t = next(t for t in pool if t.face.family is f and t.face.value == v)
        pool.remove(t)
        return t
    melds = tuple(MeldState(kind=MeldKind.PONG, tiles=tuple(take(F.DRAGON,v) for _ in range(3)),
                           claimed_from_seat_id=S[i+2], discard_sequence=i+1)
                  for i,v in enumerate(("RED","GREEN")))
    drawn = take(F.DRAGON,"WHITE")
    waiting = [take(F.DRAGON,"WHITE") for _ in range(2)] + [take(F.BAMBOO,n) for n in (1,2,3)] + [take(F.DOTS,n) for n in (1,2)]
    def fill(n):
        values=[]
        for _ in range(n):
            t=next(t for t in pool if t.face.family in {F.BAMBOO,F.DOTS,F.CHARACTERS})
            pool.remove(t);values.append(t)
        return values
    concealed=[fill(13),waiting,fill(13),fill(13)]
    players=tuple(p.model_copy(update={
        "concealed_tiles":sort_playable_tiles(concealed[i]), "drawn_tile":drawn if i==0 else None,
        "melds":melds if i==1 else (), "bonus_tiles":(),
        "initial_tile_ids":tuple(t.tile_id for t in [*concealed[i],*(t for m in melds for t in m.tiles)][:13]),
        "last_discard_face":melds[i-2].tiles[0].face if i>=2 else None,
    }) for i,p in enumerate(h.player_hands))
    discards=tuple(DiscardState(sequence=i+1,tile=m.tiles[0],discarded_by_seat_id=S[i+2],
                              claimed_by_seat_id=S[1],claim_kind=ClaimKind.PONG,live_tiles_remaining=len(pool))
                   for i,m in enumerate(melds))
    h=h.model_copy(update={"player_hands":players,"wall":WallState(live_tiles=tuple(pool[:-15]),reserve_tiles=tuple(pool[-15:])),
                           "discards":discards,"payments":(),"phase":AwaitingDiscardPhase(seat_id=S[0])})
    state=state.model_copy(update={"config":GameConfig(automatic_dragon_wins_enabled=automatic),
        "match":state.match.model_copy(update={"balances":tuple(b.model_copy(update={"points":0}) for b in state.match.balances)})})
    state=_room_with_hand(state,h,pending_deadline=None)
    validate_room(state)
    return engine,state


class HonorIntegrationTests(unittest.TestCase):
    def test_pong_records_bao_before_automatic_win_or_legacy_continuation(self):
        from app.game import Pong
        for automatic in (False,True):
            engine,state=honor_room(automatic)
            window=engine.transition(state,Discard(seat_id=S[0],tile_id=state.match.current_hand.player_hands[0].drawn_tile.tile_id)).state
            actions=engine.legal_actions(window,S[1])
            pong=next(a for a in actions if isinstance(a,Pong))
            claimed=engine.transition(window,pong).state
            resolved=engine.resolve_discard_window(claimed,claimed.match.current_hand.phase.window_id).state
            h=resolved.match.current_hand
            self.assertEqual(h.bao_liabilities[0].feeder_seat_id,S[0])
            self.assertIn("DRAGONS",h.bao_liabilities[0].reasons)
            if automatic:
                self.assertEqual(h.result.reason,"ALL_DRAGONS")
                self.assertEqual(h.settlement.final,(PayerAmount(seat_id=S[0],amount=128),))
            else:
                self.assertIsNone(h.result)
                self.assertIsNone(h.settlement)
            validate_room(resolved)

    def test_game_records_bao_and_rejects_forged_liability_state(self):
        from pydantic import ValidationError
        engine,state=honor_room(True)
        window=engine.transition(state,Discard(seat_id=S[0],tile_id=state.match.current_hand.player_hands[0].drawn_tile.tile_id)).state
        game=next(a for a in engine.legal_actions(window,S[1]) if isinstance(a,DeclareWin))
        chosen=engine.transition(window,game).state
        resolved=engine.resolve_discard_window(chosen,chosen.match.current_hand.phase.window_id).state
        h=resolved.match.current_hand
        self.assertEqual(h.settlement.liability,h.bao_liabilities[0])
        for change in ({"bao_liabilities":h.bao_liabilities*2},
                       {"bao_liabilities":(h.bao_liabilities[0].model_copy(update={"feeder_seat_id":S[2]}),)}):
            with self.assertRaises(ValidationError):
                HandState.model_validate({**h.model_dump(),**change})
