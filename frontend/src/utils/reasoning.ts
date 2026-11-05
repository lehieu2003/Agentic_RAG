import type { ReasoningStep } from '../types';

/**
 * Normalize a backend reasoning step (string or object) into a structured step.
 */
export function parseReasoningStep(step: ReasoningStep | string): ReasoningStep {
  if (typeof step !== 'string') {
    return step;
  }
  const match = step.match(/^(\d+\.?\s*[\w_]+):\s*(.*)$/);
  if (match) {
    const cleanNode = match[1].replace(/^\d+\.?\s*/, '').trim();
    return {
      node: cleanNode,
      message: match[2],
      status: 'completed',
    };
  }
  return {
    node: step,
    status: 'completed',
  };
}
