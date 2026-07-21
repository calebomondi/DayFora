import type { PropsWithChildren, ReactNode } from 'react';
import { Appearance, Pressable, StyleSheet, Text, View } from 'react-native';
import { CircleChevronLeft } from 'lucide-react-native';


export function PrimaryButton({
  children,
  onPress,
  tone = 'ink',
  disabled = false,
}: PropsWithChildren<{
  onPress: () => void;
  tone?: 'ink' | 'leaf' | 'paper';
  disabled?: boolean;
}>) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        tone === 'ink'
          ? styles.buttonink
          : tone === 'leaf'
            ? styles.buttonleaf
            : styles.buttonpaper,
        disabled && styles.buttonDisabled,
        pressed && styles.pressed,
      ]}
    >
      <Text
        style={[
          styles.buttonText,
          tone === 'paper' ? styles.buttonTextpaper : styles.buttonTextink,
        ]}
      >
        {children}
      </Text>
    </Pressable>
  );
}

export function TextButton({ children, onPress }: PropsWithChildren<{ onPress: () => void }>) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.textButtonHitArea, pressed && styles.pressed]}
    >
      <Text style={styles.textButton}>{children}</Text>
    </Pressable>
  );
}

export function ScreenSection({
  title,
  action,
  children,
}: PropsWithChildren<{ title: string; action?: ReactNode }>) {
  return (
    <View style={styles.sectionWrap}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {action}
      </View>
      <View style={styles.sectionSurface}>{children}</View>
    </View>
  );
}

export function TintedLeadingDisc({
  symbol,
  label,
  tone = 'activity',
}: {
  symbol: string;
  label: string;
  tone?: 'activity' | 'diary' | 'accent';
}) {
  return (
    <View
      accessibilityLabel={label}
      style={[
        styles.leadingDisc,
        tone === 'diary'
          ? styles.discDiary
          : tone === 'accent'
            ? styles.discAccent
            : styles.discActivity,
      ]}
    >
      <Text accessibilityElementsHidden style={styles.leadingSymbol}>
        {symbol}
      </Text>
    </View>
  );
}

export function ScreenHeader({
  eyebrow,
  title,
  onBack,
}: {
  eyebrow: string;
  title: string;
  onBack?: () => void;
}) {
  return (
    <View style={styles.header}>
      {
        onBack ? 
        <TextButton onPress={onBack}>
          <CircleChevronLeft color={colors.leaf} size={30} strokeWidth={3} style={styles.headerButton}/>
        </TextButton> : 
        null
      }
      <Text style={styles.eyebrow}>{eyebrow}</Text>
      <Text style={styles.title}>{title}</Text>
    </View>
  );
}

export function ScreenHeaderReflect({
  title,
  onBack,
}: {
  title: string;
  onBack?: () => void;
}) {
  return (
    <View style={styles.header}>
      {
        onBack ? 
        <TextButton onPress={onBack}>
          <CircleChevronLeft color={colors.leaf} size={30} strokeWidth={3} style={styles.headerButton}/>
        </TextButton> : 
        null
      }
      <Text style={styles.eyebrow}>Reflecting On</Text>
      <Text style={styles.title}>{title}</Text>
    </View>
  );
}

const isDark = Appearance.getColorScheme() === 'dark';

export const colors = isDark
  ? {
      canvas: '#101411',
      paper: '#161C18',
      surface: '#1B211D',
      ink: '#F5F7F3',
      slate: '#B9C1BB',
      line: '#2C352E',
      leaf: '#69C87E',
      accentWash: '#1C3522',
      diary: '#2A2535',
      activity: '#1C3522',
      sky: '#202A31',
      sun: '#4A4224',
      coral: '#D19A87',
      selectedDayWash: '#1C3522',
      selectedDayInk: '#B7EDC3',
      red: '#ff0000',
      orange: "#FFD7B5"
    }
  : {
      canvas: '#F8F7F0',
      paper: '#FFFEFA',
      surface: '#F1F0F5',
      ink: '#202322',
      slate: '#626866',
      line: '#E1E1DD',
      leaf: '#4CAE63',
      accentWash: '#E3F3E6',
      diary: '#EEEAF7',
      activity: '#E1F1E7',
      sky: '#E9F0F8',
      sun: '#F3E7B7',
      coral: '#C98974',
      selectedDayWash: 'rgba(76, 174, 99, 0.18)',
      selectedDayInk: '#246B39',
      red: '#ff0000',
      orange: "#FFD7B5"
    };

const styles = StyleSheet.create({
  headerButton: {backgroundColor: colors.accentWash, borderRadius: 999},
  header: { gap: 7, marginBottom: 26 },
  eyebrow: { color: colors.slate, fontSize: 18, fontWeight: '600', marginTop: 8 },
  title: {
    color: colors.ink,
    fontSize: 28,
    fontFamily: 'Kalam_700Bold', 
    letterSpacing: -0.9,
    lineHeight: 38,
  },
  button: {
    alignItems: 'center',
    borderRadius: 999,
    minHeight: 52,
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  buttonink: { backgroundColor: colors.ink },
  buttonleaf: { backgroundColor: colors.leaf },
  buttonpaper: { backgroundColor: '#FFFEFA', borderColor: '#DCE4DD', borderWidth: 1 },
  buttonDisabled: { opacity: 0.42 },
  buttonText: { fontSize: 17, fontWeight: '700' },
  buttonTextink: { color: '#FFFFFF' },
  buttonTextleaf: { color: '#FFFFFF' },
  buttonTextpaper: { color: '#172B35' },
  textButtonHitArea: {
    alignSelf: 'flex-start',
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: 4,
  },
  textButton: { color: colors.leaf, fontSize: 15, fontWeight: '700' },
  pressed: { opacity: 0.68 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  badge: { borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5 },
  badgeuser_written: { backgroundColor: colors.accentWash },
  badgetranscribed: { backgroundColor: colors.diary },
  badgeai_generated: { backgroundColor: colors.surface },
  badgeText: { color: colors.leaf, fontSize: 15, fontWeight: '600' },
  sectionWrap: { gap: 8, marginTop: 28 },
  sectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 28,
  },
  sectionTitle: { color: colors.slate, fontSize: 15, fontWeight: '600' },
  sectionSurface: { backgroundColor: colors.surface, borderRadius: 22, overflow: 'hidden' },
  leadingDisc: {
    alignItems: 'center',
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  discActivity: { backgroundColor: colors.activity },
  discDiary: { backgroundColor: colors.diary },
  discAccent: { backgroundColor: colors.accentWash },
  leadingSymbol: { color: colors.ink, fontSize: 18, fontWeight: '700' },
});
