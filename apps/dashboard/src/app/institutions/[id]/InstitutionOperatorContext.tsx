"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { persistOperatorToken, removeOperatorToken, restoreOperatorToken } from "@/lib/operator-session";

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

  useEffect(() => {
    const restoreTimer = window.setTimeout(() => {
      const token = restoreOperatorToken();
      if (!token) return;
      setOperatorToken(token);
      setOperatorReady(true);
    }, 0);
    return () => window.clearTimeout(restoreTimer);
  }, []);

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
      persistOperatorToken(token);
      setOperatorToken(token);
      setOperatorReady(true);
      return true;
    },
    deactivateOperator() {
      removeOperatorToken();
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
