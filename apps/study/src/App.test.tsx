import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { ApiError, type Condition, type Enrollment, type StudyApi, type StudyEventType, type TrialRecord } from './api';
import { loadPracticeItems, loadStudyItems, type StudyItem } from './items';
import { Outbox } from './outbox';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const study = loadStudyItems();
const practice = loadPracticeItems();
// Three main items: a flagged wrong answer, a correct high one, a wrong high one.
const flaggedWrong = study.find((item) => !item.ai_is_correct && item.signal.flagged_sentence_indices.length > 0)!;
const correctHigh = study.find((item) => item.ai_is_correct && item.signal.level === 'high')!;
const wrongHigh = study.find((item) => !item.ai_is_correct && item.signal.level === 'high')!;
const ITEMS: StudyItem[] = [flaggedWrong, correctHigh, wrongHigh];

interface Recorded {
  trials: TrialRecord[];
  questionnaires: Array<[string, Record<string, number | string>]>;
  events: Array<[StudyEventType, Record<string, string>]>;
}

function fakeApi(condition: Condition, overrides: Partial<StudyApi> = {}): StudyApi & { recorded: Recorded } {
  const recorded: Recorded = { trials: [], questionnaires: [], events: [] };
  const enrollment: Enrollment = { participantId: 'p-1', token: 't', condition, consentVersion: 'v1' };
  return {
    demo: false,
    recorded,
    enroll: vi.fn(async () => enrollment),
    postTrial: async (_e, trial) => void recorded.trials.push(trial),
    postQuestionnaire: async (_e, instrument, responses) => void recorded.questionnaires.push([instrument, responses]),
    postEvent: async (_e, type, metadata) => void recorded.events.push([type, metadata]),
    deleteParticipant: vi.fn(async () => {}),
    ...overrides,
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  window.scrollTo = () => {};
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const settle = async () => {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
};
const heading = () => container.querySelector('h1')!.textContent;
const button = (text: string) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement;
async function click(element: Element) {
  await act(async () => {
    (element as HTMLElement).click();
  });
  await settle();
}
async function choose(text: string, scope: ParentNode = container) {
  const label = [...scope.querySelectorAll('label')].find((l) => l.textContent?.includes(text))!;
  await click(label.querySelector('input')!);
}
const overlayHost = () => container.querySelector('[data-calibrai-overlay]');

async function render(api: StudyApi, outbox?: Outbox) {
  await act(async () => {
    root.render(
      <App api={api} enrollmentCode="CODE" consentVersion="v1" items={ITEMS} practiceItems={practice} outbox={outbox} random={() => 0.99} />,
    );
  });
}

async function throughPractice(api: StudyApi) {
  await render(api);
  expect(heading()).toBe('Judging AI answers: a short study');
  expect(button('Start').disabled).toBe(true);
  await click(container.querySelector('input[type=checkbox]')!);
  await click(button('Start'));
  expect(heading()).toBe('About you');
  await choose('25–34');
  await choose('Some');
  await click(button('Continue'));
  expect(heading()).toBe('How it works');
  await click(button('Start the practice'));
  for (let i = 0; i < 2; i += 1) {
    expect(heading()).toBe(`Practice ${i + 1} of 2`);
    await choose('Accept');
    await choose('Very');
    await click(button('Next'));
  }
  expect(heading()).toBe('Practice done');
  await click(button('Start'));
}

async function answerTrial(decision: 'Accept' | 'Reject', confidence: string) {
  await choose(decision);
  await choose(confidence);
  await click(button('Next'));
}

async function finishQuestionnaire() {
  expect(heading()).toBe('Almost done');
  for (const fieldset of container.querySelectorAll('fieldset.likert')) {
    await click(fieldset.querySelectorAll('input')[4]);
  }
  await click(button('Finish'));
}

describe('study flow', () => {
  it('condition C: pill + underlined flagged sentences, logs main trials only, then debriefs', async () => {
    const api = fakeApi('C');
    await throughPractice(api);

    // Order with random() = 0.99: Fisher-Yates keeps the input order.
    expect(heading()).toBe('Question 1 of 3');
    expect(overlayHost()?.shadowRoot?.querySelector('.calibrai-pill')).toBeTruthy();
    const flagged = container.querySelectorAll('.flagged');
    expect(flagged.length).toBe(flaggedWrong.signal.flagged_sentence_indices.length);
    const tip = flagged[0].querySelector('[role=tooltip]') as HTMLElement;
    expect(flagged[0].getAttribute('tabindex')).toBe('0');
    expect(flagged[0].getAttribute('aria-describedby')).toBe(tip.id);
    expect(tip.hidden).toBe(true);
    await act(async () => (flagged[0] as HTMLElement).focus());
    expect(tip.hidden).toBe(false);
    expect(tip.textContent).toContain('Flagged by the checker');
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(tip.hidden).toBe(true);

    // Opening the pill's details is logged too.
    await click(overlayHost()!.shadowRoot!.querySelector('button.calibrai-pill')!);

    await answerTrial('Reject', 'Completely');
    await answerTrial('Accept', 'Very');
    await answerTrial('Accept', 'Slightly');
    await finishQuestionnaire();
    expect(heading()).toBe('Thank you');
    expect(container.textContent).toContain('All your answers are saved.');
    expect(container.textContent).toContain('right exactly 70% of the time');

    const { trials, questionnaires, events } = api.recorded;
    expect(trials.map((t) => [t.question_id, t.position, t.decision, t.self_confidence, t.final_correct])).toEqual([
      [flaggedWrong.id, 0, 'reject', 5, true],
      [correctHigh.id, 1, 'accept', 4, true],
      [wrongHigh.id, 2, 'accept', 2, false],
    ]);
    expect(trials.every((t) => t.condition === 'C' && Date.parse(t.decided_at) >= Date.parse(t.shown_at))).toBe(true);
    expect(trials[0]).toMatchObject({ ai_correct: false, signal_level: flaggedWrong.signal.level, signal_score: flaggedWrong.signal.score });
    expect(questionnaires).toEqual([
      ['demographics', { age_band: '25-34', ai_experience: 3 }],
      ['trust', { trust_1: 5, trust_2: 5, trust_3: 5, trust_4: 5, trust_5: 5 }],
    ]);
    // Practice is not logged: every event belongs to a main trial.
    expect(events.every(([, metadata]) => metadata.phase === 'main' && ITEMS.some((i) => i.id === metadata.question_id))).toBe(true);
    const types = events.map(([type]) => type);
    expect(types.filter((type) => type === 'signal_shown')).toHaveLength(3);
    expect(types).toContain('explanation_opened');
    expect(events.find(([type]) => type === 'tooltip_opened')![1]).toMatchObject({
      question_id: flaggedWrong.id,
      condition: 'C',
      sentence_index: String(flaggedWrong.signal.flagged_sentence_indices[0]),
    });
  });

  it('condition A: the pill but no underlines', async () => {
    const api = fakeApi('A');
    await throughPractice(api);
    expect(overlayHost()?.shadowRoot?.querySelector('.calibrai-pill')).toBeTruthy();
    expect(container.querySelector('.flagged')).toBeNull();
  });

  it('baseline: no signal at all, and the instructions never mention one', async () => {
    const api = fakeApi('baseline');
    await render(api);
    await click(container.querySelector('input[type=checkbox]')!);
    await click(button('Start'));
    await choose('25–34');
    await choose('Some');
    await click(button('Continue'));
    expect(container.textContent).not.toMatch(/checker|label/i);
    await click(button('Start the practice'));
    expect(overlayHost()).toBeNull();
    expect(container.querySelector('.flagged')).toBeNull();
    await answerTrial('Accept', 'Very');
    await answerTrial('Accept', 'Very');
    await click(button('Start'));
    await answerTrial('Accept', 'Very');
    expect(api.recorded.events).toEqual([]);
    expect(api.recorded.trials[0]).toMatchObject({ condition: 'baseline', signal_level: flaggedWrong.signal.level });
  });

  it('retries a failed save quietly and never loses the trial', async () => {
    let failures = 2;
    const api = fakeApi('A');
    const realPost = api.postTrial;
    api.postTrial = async (enrollment, trial) => {
      if (failures-- > 0) throw new ApiError(503, 'busy');
      return realPost(enrollment, trial);
    };
    const waits: Array<() => void> = [];
    const outbox = new Outbox({ wait: () => new Promise<void>((resolve) => waits.push(resolve)) });
    await render(api, outbox);
    await click(container.querySelector('input[type=checkbox]')!);
    await click(button('Start'));
    await choose('25–34');
    await choose('Some');
    await click(button('Continue'));
    await click(button('Start the practice'));
    await answerTrial('Accept', 'Very');
    await answerTrial('Accept', 'Very');
    await click(button('Start'));
    await answerTrial('Reject', 'Very');
    expect(container.querySelector('.saving')!.textContent).toBe('Saving… (connection problem, retrying)');
    expect(api.recorded.trials).toEqual([]);
    await act(async () => waits.shift()!());
    await settle();
    await act(async () => waits.shift()!());
    await settle();
    expect(api.recorded.trials.map((t) => t.question_id)).toEqual([flaggedWrong.id]);
    expect(container.querySelector('.saving')!.textContent).toBe('');
  });

  it('shows, and offers to download, a record the server refused', async () => {
    const api = fakeApi('baseline', {
      postQuestionnaire: async () => {
        throw new ApiError(422, 'trust needs exactly 5 items');
      },
    });
    await render(api);
    await click(container.querySelector('input[type=checkbox]')!);
    await click(button('Start'));
    await choose('25–34');
    await choose('Some');
    await click(button('Continue'));
    expect(container.querySelector('.saving')!.textContent).toBe("Some answers couldn't be saved");
  });

  it('explains enrollment problems on the consent page', async () => {
    const api = fakeApi('A', {
      enroll: async () => {
        throw new ApiError(401, 'Invalid study enrollment code');
      },
    });
    await render(api);
    await click(container.querySelector('input[type=checkbox]')!);
    await click(button('Start'));
    expect(heading()).toBe('Judging AI answers: a short study');
    expect(container.querySelector('[role=alert]')!.textContent).toContain('invalid access code');
  });

  it('lets the participant stop and delete their answers', async () => {
    const api = fakeApi('C');
    await render(api);
    await click(container.querySelector('input[type=checkbox]')!);
    await click(button('Start'));
    await click(button('Stop'));
    expect(heading()).toBe('Stop the study?');
    await click(button('Stop and delete my answers'));
    expect(api.deleteParticipant).toHaveBeenCalledOnce();
    expect(heading()).toBe("You've stopped the study");
    expect(container.textContent).toContain('has been deleted');
  });
});
