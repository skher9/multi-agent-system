"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Credits = components["schemas"]["Credits"];

/** The account's free runs (left is null: no limit), and a way to count one as used. */
export function useCredits() {
  const [credits, setCredits] = useState<Credits | null>(null);
  useEffect(() => {
    api.GET("/me/credits").then(({ data }) => data && setCredits(data));
  }, []);
  const spendOne = () => setCredits((c) => (c?.left ? { ...c, left: c.left - 1 } : c));
  return { credits, spendOne };
}
