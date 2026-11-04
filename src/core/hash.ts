const encoder = new TextEncoder();

export async function hashAnswer(answer: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', encoder.encode(answer.trim()));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}
