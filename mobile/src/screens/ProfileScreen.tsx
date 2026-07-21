import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { LogOut, ShieldCheck, UserRound } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ScreenHeader, ScreenSection, TintedLeadingDisc, colors } from '../components/ui';

type ProfileScreenProps = {
  displayName: string;
  email?: string;
  onBack: () => void;
  onSignOut: () => void;
};

/** A small account destination until richer privacy/data controls are implemented. */
export function ProfileScreen({ displayName, email, onBack, onSignOut }: ProfileScreenProps) {
  const insets = useSafeAreaInsets();
  
  return (
    <ScrollView contentContainerStyle={[styles.container, { paddingTop: insets.top + 12 }]} contentInsetAdjustmentBehavior="automatic">
      <ScreenHeader eyebrow="Your private space" title="Profile" onBack={onBack} />
      <ScreenSection title="Account">
        <View style={styles.profileRow}>
          <View style={styles.personDisc}>
            <UserRound color={colors.ink} size={22} strokeWidth={2} />
          </View>
          <View style={styles.copy}>
            <Text selectable style={styles.name}>{displayName}</Text>
            {email ? <Text selectable style={styles.email}>{email}</Text> : null}
          </View>
        </View>
      </ScreenSection>
      <ScreenSection title="Privacy & data">
        <View style={styles.infoRow}>
          <TintedLeadingDisc label="Private by default" symbol="•" tone="accent" />
          <View style={styles.copy}>
            <Text selectable style={styles.infoTitle}>Private by default</Text>
            <Text selectable style={styles.infoCopy}>
              Your diary, evidence, and media remain private to your account.
            </Text>
          </View>
          <ShieldCheck accessibilityElementsHidden color={colors.slate} size={20} strokeWidth={2} />
        </View>
        <View style={styles.placeholder}>
          <Text selectable style={styles.placeholderTitle}>Your data controls</Text>
          <Text selectable style={styles.placeholderCopy}>
            Export and deletion controls will appear here as they become available.
          </Text>
        </View>
      </ScreenSection>
      <Pressable
        accessibilityHint="Signs out on this device"
        accessibilityLabel="Sign out"
        accessibilityRole="button"
        onPress={onSignOut}
        style={({ pressed }) => [styles.signOut, pressed && styles.pressed]}
      >
        <LogOut color={colors.slate} size={20} strokeWidth={2} />
        <Text style={styles.signOutText}>Sign out</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { backgroundColor: colors.canvas, flexGrow: 1, gap: 18, padding: 24, paddingBottom: 48 },
  profileRow: { alignItems: 'center', flexDirection: 'row', gap: 13, padding: 16 },
  personDisc: { alignItems: 'center', backgroundColor: colors.accentWash, borderRadius: 24, height: 48, justifyContent: 'center', width: 48 },
  copy: { flex: 1, gap: 3 },
  name: { color: colors.ink, fontSize: 17, fontWeight: '700' },
  email: { color: colors.slate, fontSize: 14 },
  infoRow: { alignItems: 'center', flexDirection: 'row', gap: 12, minHeight: 80, padding: 16 },
  infoTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  infoCopy: { color: colors.slate, fontSize: 14, lineHeight: 19 },
  placeholder: { borderTopColor: colors.line, borderTopWidth: StyleSheet.hairlineWidth, gap: 4, padding: 16 },
  placeholderTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  placeholderCopy: { color: colors.slate, fontSize: 14, lineHeight: 19 },
  signOut: { alignItems: 'center', alignSelf: 'flex-start', borderRadius: 22, flexDirection: 'row', gap: 8, minHeight: 44, paddingHorizontal: 12 },
  signOutText: { color: colors.slate, fontSize: 16, fontWeight: '700' },
  pressed: { backgroundColor: colors.surface },
});
