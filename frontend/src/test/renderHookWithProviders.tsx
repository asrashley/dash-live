import type { JSX, ComponentChildren } from "preact";
import { renderWithProviders, RenderWithProvidersProps } from "./renderWithProviders";

function DefaultWrapper({ children }: { children: ComponentChildren }) {
  return <div>{children}</div>;
}

export function renderHookWithProviders<Props, Output>(
  hook: (props: Props) => Output,
  {
    initialState,
    Wrapper = DefaultWrapper,
    ...props
  }: Partial<
    RenderWithProvidersProps & {
      initialState: Props;
      Wrapper: (props: { children: ComponentChildren }) => JSX.Element;
    }
  > = {}
) {
  let result: Output;

  function HookWrapper({ text }: { text: string }) {
    result = hook(initialState);
    return <div>{text}</div>;
  }
  const now = new Date().toISOString();
  const { getByText, rerender } = renderWithProviders(
    <Wrapper>
      <HookWrapper text={now} />
    </Wrapper>,
    props
  );
  getByText(now);
  return { result, rerender };
}
