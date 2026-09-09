import { createContext, createElement, useContext, type ReactNode } from "react";

export interface TranslateArgs {
  /** TanStack field name (e.g. "editor.title"). */
  field: string;
  text?: string;
  texts?: string[];
}

export interface TranslateResult {
  text?: string | null;
  texts?: (string | null)[] | null;
}

export type SchemaFormTranslate = (args: TranslateArgs) => Promise<TranslateResult | null>;

const TranslateContext = createContext<SchemaFormTranslate | null>(null);

export function SchemaFormTranslateProvider({
  onTranslate,
  children,
}: {
  onTranslate?: SchemaFormTranslate;
  children: ReactNode;
}) {
  return createElement(TranslateContext.Provider, { value: onTranslate ?? null }, children);
}

export function useSchemaFormTranslate(): SchemaFormTranslate | null {
  return useContext(TranslateContext);
}
