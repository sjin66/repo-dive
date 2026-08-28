export class Service {
  run(value: number): number {
    return helper(value);
  }
}

export function helper(value: number): number {
  return value + 1;
}
