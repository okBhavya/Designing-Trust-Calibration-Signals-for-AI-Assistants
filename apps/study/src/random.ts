/** A uniform float in [0, 1) from the platform CSPRNG. */
export function cryptoRandom(): number {
  const buffer = new Uint32Array(1);
  crypto.getRandomValues(buffer);
  return buffer[0] / 2 ** 32;
}

/** Fisher-Yates shuffle; returns a new array. */
export function shuffle<T>(items: readonly T[], random: () => number = cryptoRandom): T[] {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}
