import React from "react";
import { render, screen } from "@testing-library/react";
import { GenerationStatus, inferResponseContract, ResponseContent } from "./Results";

test("quota fallback shows a safe status without raw provider details", () => {
  render(<GenerationStatus mode="extractive_fallback" diagnostics={{ quota_exhausted: true, gemini_error: "secret provider exception" }} />);
  expect(screen.getByText("Retrieval-only fallback")).toBeInTheDocument();
  expect(screen.getByText(/model service quota has been reached/i)).toBeInTheDocument();
  expect(screen.queryByText(/secret provider exception/i)).not.toBeInTheDocument();
});

test.each([
  ["gemini_structured", "AI-generated structured interpretation"],
  ["gemini_degraded", "AI-generated degraded interpretation"],
  ["extractive_fallback", "Retrieval-only fallback"],
])("labels %s result mode", (mode, label) => {
  render(<GenerationStatus mode={mode} />);
  expect(screen.getByText(label)).toBeInTheDocument();
});

test("general answers render conversationally without report headings", () => {
  render(<ResponseContent contract="general" structuredAnswer={{ answer: "HER2 is a receptor protein.", limitations: [], reference_citations: [] }} />);
  expect(screen.getByText("HER2 is a receptor protein.")).toBeInTheDocument();
  expect(screen.queryByText(/findings at a glance/i)).not.toBeInTheDocument();
});

test("focused answers render answer certainty and U citations", () => {
  render(<ResponseContent contract="focused" structuredAnswer={{ answer: "The liver lesion is indeterminate.", certainty: "indeterminate", citations: ["U1"] }} />);
  expect(screen.getByText("The liver lesion is indeterminate.")).toBeInTheDocument();
  expect(screen.getByText("indeterminate")).toBeInTheDocument();
  expect(screen.getByText("U1")).toBeInTheDocument();
});

test("full report answers render canonical clinical sections", () => {
  render(<ResponseContent contract="full_report" structuredAnswer={{
    headline: "Clinical summary", plain_language_summary: "Plain explanation.",
    evidence_support: { level: "Limited", explanation: "One report." },
    key_findings: [{ title: "Finding", result: "Result", meaning: "Meaning", citations: ["U1"] }],
    staging: { explanation: "A final stage cannot be assigned." },
    limitations: ["Clinical review is required."], medical_terms: [], safety_notice: "Professional review is required.",
  }} />);
  expect(screen.getByText("In simple terms")).toBeInTheDocument();
  expect(screen.getByText("Findings at a glance")).toBeInTheDocument();
  expect(screen.getByText("Staging")).toBeInTheDocument();
  expect(screen.getByText("Important limitations")).toBeInTheDocument();
  expect(screen.getByText("Professional review is required.")).toBeInTheDocument();
});

test("historical full report without response_contract is inferred safely", () => {
  const historical = { plain_language_summary: "Legacy explanation.", findings: [] };
  expect(inferResponseContract(undefined, historical)).toBe("full_report");
  render(<ResponseContent contract={inferResponseContract(undefined, historical)} structuredAnswer={historical} summary="Fallback" />);
  expect(screen.getByText("Legacy explanation.")).toBeInTheDocument();
});
