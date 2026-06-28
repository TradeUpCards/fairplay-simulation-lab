import { Slide, Lead, Pill, Bullets } from '../Slide'
import type { SlideDef } from '../types'

function QuestionSlide() {
  return (
    <Slide center>
      <div className="flex flex-col gap-7">
        <div className="font-mono text-[0.8rem] uppercase tracking-[0.28em] text-brass">
          The question
        </div>
        <h2 className="m-0 max-w-[20ch] text-[3rem] font-bold leading-[1.05] tracking-[-0.01em] text-text">
          How do we increase play time?
        </h2>

        <div className="flex items-center gap-3">
          <span className="text-[1.05rem] text-muted">Our north star:</span>
          <Pill tone="brass">paid seat-hours</Pill>
        </div>

        <div className="max-w-[60ch]">
          <Lead>The enemy of seat-time is an unhealthy table.</Lead>
          <div className="mt-5">
            <Bullets
              items={[
                'Recreational players seated into predatory mixes lose their stack fast.',
                'They tilt, they bust, they leave early — and they don’t come back.',
                'A table can churn hands and still empty the room. Hands ≠ retained time.',
              ]}
            />
          </div>
        </div>
      </div>
    </Slide>
  )
}

export const questionSlide: SlideDef = {
  id: 'question',
  label: 'The question',
  Component: QuestionSlide,
}
