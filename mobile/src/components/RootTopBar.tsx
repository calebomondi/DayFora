import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Settings, UserRound } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from './ui';

type RootTopBarProps = {
  onOpenProfile: () => void;
  onOpenSettings: () => void;
};

/** The one account/brand header shared by the signed-in root tabs. */
export function RootTopBar({ onOpenProfile, onOpenSettings }: RootTopBarProps) {
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.bar, { paddingTop: insets.top + 6 }]}>
      <Text accessibilityRole="header" style={styles.wordmark}>
        DayFora
      </Text>
      <View style={styles.actions}>
        <Pressable
          accessibilityHint="Opens your account"
          accessibilityLabel="Profile"
          accessibilityRole="button"
          onPress={onOpenProfile}
          style={({ pressed }) => [styles.action, pressed && styles.pressed]}
        >
          <UserRound color={colors.leaf} size={25} strokeWidth={2} />
        </Pressable>
        <Pressable
          accessibilityHint="Opens settings"
          accessibilityLabel="Settings"
          accessibilityRole="button"
          onPress={onOpenSettings}
          style={({ pressed }) => [styles.action, pressed && styles.pressed]}
        >
          <Settings color={colors.leaf} size={25} strokeWidth={2} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    alignItems: 'center',
    backgroundColor: colors.canvas,
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 58,
    paddingBottom: 8,
    paddingHorizontal: 24,
  },
  wordmark: {
    color: colors.leaf,
    fontSize: 30,
    fontFamily: 'ABeeZee_400Regular',
    letterSpacing: -0.4,
  },
  actions: { alignItems: 'center', flexDirection: 'row', gap: 3 },
  action: {
    alignItems: 'center',
    borderRadius: 999,
    backgroundColor: colors.accentWash,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  pressed: { backgroundColor: colors.accentWash },
});
