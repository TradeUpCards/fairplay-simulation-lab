import { Slide, Card, Columns, Bullets } from "../Slide";
import type { SlideDef } from "../types";

function IntelligenceSlide() {
  return (
    <Slide kicker="Under the hood" title="The intelligence behind the table">
      <div className="flex flex-col gap-7">
        <Columns cols={2}>
          <Card>
            <div className="font-mono text-[0.78rem] uppercase tracking-[0.2em] text-muted">
              Table health
            </div>
            <p className="mt-2 text-[0.95rem] text-faint">
              Why a table is decaying
            </p>
            <div className="mt-3">
              <Bullets
                items={[
                  "Predation",
                  "Fragility",
                  "Clustering",
                  "Recreational bleed",
                ]}
              />
            </div>
          </Card>
          <Card>
            <div className="font-mono text-[0.78rem] uppercase tracking-[0.2em] text-muted">
              Integrity signals
            </div>
            <p className="mt-2 text-[0.95rem] text-faint">
              Simulated fields, not real detection
            </p>
            <div className="mt-3">
              <Bullets
                items={[
                  "Bot-similarity score",
                  "Soft-play delta",
                  "Mocked device clusters",
                ]}
              />
            </div>
          </Card>
        </Columns>

        <Card brassTop>
          <div className="text-[1.2rem] font-semibold text-text">
            The LLM is never the detector.
          </div>
          <p className="mt-3 max-w-[70ch] text-[1rem] leading-relaxed text-muted">
            Structured scoring finds risk. The AI Investigator receives a
            structured <span className="text-brass">evidence packet only</span>{" "}
            — never raw player data — and explains it: with uncertainty
            language, surfacing counter-evidence, and always recommending a
            human action. &ldquo;Elevated for review,&rdquo; never &ldquo;these
            players cheated.&rdquo;
          </p>
        </Card>
      </div>
    </Slide>
  );
}

export const intelligenceSlide: SlideDef = {
  id: "intelligence",
  label: "The intelligence",
  Component: IntelligenceSlide,
};
