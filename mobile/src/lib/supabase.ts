import 'react-native-url-polyfill/auto';
import { Platform } from 'react-native';
import { createClient } from '@supabase/supabase-js';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error('Missing EXPO_PUBLIC_SUPABASE_URL or EXPO_PUBLIC_SUPABASE_ANON_KEY');
}

const storageAdapter = Platform.OS === 'web'
  ? { getItem: (key: string) => Promise.resolve(localStorage.getItem(key)), setItem: (key: string, value: string) => Promise.resolve(localStorage.setItem(key, value)), removeItem: (key: string) => Promise.resolve(localStorage.removeItem(key)) }
  : require('@react-native-async-storage/async-storage').default;

export const supabase = createClient(url, anonKey, {
  auth: { autoRefreshToken: true, persistSession: true, storage: storageAdapter },
});
