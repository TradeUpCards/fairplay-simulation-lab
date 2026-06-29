import logo from "../../assets/fairplay-iq-logo-brass.svg";
import { Slide } from "../Slide";
import type { SlideDef } from "../types";

function TitleSlide() {
  return (
    <Slide center>
      <div className="flex flex-col items-start gap-6">
        <img className="h-[64px] w-auto" src={logo} alt="FairPlay IQ" />
        <h1 className="m-0 text-[3.4rem] font-bold leading-[1.05] tracking-[-0.01em] text-text">
          Increasing player seat time through
          <br />
          table health optimization.
        </h1>
        <p className="m-0 max-w-[46ch] text-[1.4rem] leading-snug text-muted">
          An AI simulation lab and operator copilot for online-poker table
          health and integrity.
        </p>
      </div>
    </Slide>
  );
}

export const titleSlide: SlideDef = {
  id: "title",
  label: "FairPlay IQ",
  Component: TitleSlide,
};
