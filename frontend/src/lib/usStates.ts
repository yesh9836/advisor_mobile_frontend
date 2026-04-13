import usStates from "../../../shared/us_states.json";

export interface UsStateOption {
  code: string;
  label: string;
}

export const US_STATE_OPTIONS: ReadonlyArray<UsStateOption> = usStates;
