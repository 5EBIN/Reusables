// GENERATED. Do not edit.
import type { Metadata } from "next";
import { Suspense } from "react";
import { Shell } from "@/components/Shell";
import Loading from "../loading";
import Content from "./content";
import { load } from "@/lib/loaders/approvals";

export const metadata: Metadata = { title: "Approvals — Acme" };

export const dynamic = "force-dynamic";

async function Body({ p }: { p: ReturnType<typeof load> }) {
  return <Content d={await p} />;
}

export default async function ApprovalsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const p = load(await searchParams);
  p.catch(() => undefined);                                         // awaited in <Body>; this only keeps an early rejection from being reported twice
  return <Shell active="approvals"><Suspense fallback={<Loading />}><Body p={p} /></Suspense></Shell>;
}
