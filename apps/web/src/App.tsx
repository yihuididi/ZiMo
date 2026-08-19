import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "./routes/HomePage";
import { NotFoundPage } from "./routes/NotFoundPage";
import { RoomRoute } from "./routes/RoomPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/rooms/:roomId" element={<RoomRoute />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
