import {
  type ComponentPropsWithoutRef,
  useEffect,
  useRef,
} from "react";

interface PageHeadingProps extends ComponentPropsWithoutRef<"h1"> {
  focusOnMount?: boolean;
}

export function PageHeading({
  focusOnMount = false,
  ...props
}: PageHeadingProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (focusOnMount) headingRef.current?.focus();
  }, [focusOnMount]);

  return (
    <h1
      {...props}
      ref={headingRef}
      tabIndex={focusOnMount ? -1 : props.tabIndex}
    />
  );
}
