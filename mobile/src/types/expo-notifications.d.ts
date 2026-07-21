// Type declarations for push notification packages installed via
// `npx expo install expo-notifications expo-device`
// These are dynamic imports; the bundler resolves them at runtime.
declare module 'expo-notifications' {
  export function getPermissionsAsync(): Promise<{ status: string }>;
  export function requestPermissionsAsync(): Promise<{ status: string }>;
  export function getExpoPushTokenAsync(): Promise<{ data: string }>;
  export function setNotificationChannelAsync(channelId: string, channel: { name: string; importance: number }): Promise<void>;
  export const AndroidImportance: { MAX: number };
}

declare module 'expo-device' {
  export const isDevice: boolean;
}
