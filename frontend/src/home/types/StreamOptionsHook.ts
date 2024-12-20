import { createContext } from "preact";
import { UseStreamOptionsHook } from "../hooks/useStreamOptions";

export const StreamOptionsContext = createContext<UseStreamOptionsHook>(null);
