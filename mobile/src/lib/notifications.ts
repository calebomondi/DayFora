import { Platform } from 'react-native';
import type { Session } from '@supabase/supabase-js';
import * as Device from 'expo-device';
import Constants, { AppOwnership } from 'expo-constants';

import { registerDeviceToken } from './api';

export async function registerForPushNotifications(session: Session): Promise<void> {
  // Android remote notifications are not available in Expo Go from SDK 53.
  // This must happen before importing expo-notifications, whose import itself
  // emits an unsupported-runtime error in Expo Go.
  if (Constants.appOwnership === AppOwnership.Expo) {
    return;
  }

  if (!Device.isDevice) {
    return;
  }

  try {
    const Notifications = await import('expo-notifications');

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;

    if (existing !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') {
      console.log('Notification permissions not granted');
      return;
    }

    const tokenData = await Notifications.getExpoPushTokenAsync();
    const platform = Platform.OS === 'android' ? 'android' : 'ios';

    await registerDeviceToken(session, {
      expo_push_token: tokenData.data,
      platform,
    });

    if (Platform.OS === 'android') {
      Notifications.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.AndroidImportance.MAX,
      });
    }
  } catch (err) {
    console.log('Push notification registration skipped:', err);
  }
}
