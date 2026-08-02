"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type InstitutionOperatorContextValue = {
  operatorToken: string;
  operatorReady: boolean;
  updateOperatorToken: (token: string) => void;
  activateOperator: () => boolean;
  deactivateOperator: () => void;
};

const InstitutionOperatorContext = createContext<InstitutionOperatorContextValue | null>(null);

export function InstitutionOperatorProvider({ children }: { children: ReactNode }) {
  const [operatorToken, setOperatorToken] = useState("");
  const [operatorReady, setOperatorReady] = useState(false);

  const value = useMemo<InstitutionOperatorContextValue>(() => ({
    operatorToken,
    operatorReady,
    updateOperatorToken(token) {
      setOperatorToken(token);
      setOperatorReady(false);
    },
    activateOperator() {
      const token = operatorToken.trim();
      if (!token) return false;
      setOperatorToken(token);
      setOperatorReady(true);
      return true;
    },
    deactivateOperator() {
      setOperatorToken("");
      setOperatorReady(false);
    },
  }), [operatorReady, operatorToken]);

  return <InstitutionOperatorContext.Provider value={value}>{children}</InstitutionOperatorContext.Provider>;
}

export function useInstitutionOperator() {
  const context = useContext(InstitutionOperatorContext);
  if (!context) throw new Error("useInstitutionOperator must be used within InstitutionOperatorProvider");
  return context;
}
