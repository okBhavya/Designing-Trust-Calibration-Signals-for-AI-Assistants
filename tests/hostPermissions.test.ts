import { describe, expect, it } from 'vitest';
import { hostPermissions, LOCAL_API_HOST_PERMISSIONS, parseApiOrigin, SITE_HOST_PERMISSIONS } from '../src/core/hostPermissions';

describe('host permissions', () => {
  it('production: the chat sites and the configured API only', () => {
    expect(hostPermissions('https://calibrai-api.onrender.com', 'production')).toEqual([
      ...SITE_HOST_PERMISSIONS,
      'https://calibrai-api.onrender.com/*',
    ]);
  });

  it('production without an API origin: no API host at all (mock mode only)', () => {
    expect(hostPermissions(undefined, 'production')).toEqual(SITE_HOST_PERMISSIONS);
    expect(hostPermissions('  ', 'production')).toEqual(SITE_HOST_PERMISSIONS);
  });

  it('development keeps the local API ports', () => {
    expect(hostPermissions(undefined, 'development')).toEqual([...SITE_HOST_PERMISSIONS, ...LOCAL_API_HOST_PERMISSIONS]);
    expect(hostPermissions('https://api.example.org', 'development')).toContain('https://api.example.org/*');
  });

  it('never ships the old placeholder domain', () => {
    for (const mode of ['production', 'development']) {
      expect(hostPermissions(undefined, mode).join(' ')).not.toContain('calibrai.example');
    }
  });

  it.each([
    ['https://api.example.org/', 'https://api.example.org'],
    ['https://api.example.org:8443', 'https://api.example.org:8443'],
    [' https://API.example.org ', 'https://api.example.org'],
  ])('normalizes %j', (input, expected) => {
    expect(parseApiOrigin(input)).toBe(expected);
  });

  it.each(['http://api.example.org', 'https://api.example.org/v1', 'https://api.example.org/?x=1', 'api.example.org', 'not a url'])(
    'rejects %j',
    (input) => {
      expect(() => parseApiOrigin(input)).toThrow(/WXT_API_ORIGIN/);
    },
  );
});
