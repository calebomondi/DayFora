import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Compass, PencilLine } from 'lucide-react-native';
import React from 'react';
import { colors } from './ui';

export type MainTab = 'diary' | 'explore';

const tabs: { id: MainTab; label: string; symbol: React.ReactNode }[] = [
  { id: 'explore', label: 'Explore You', symbol: <Compass color={colors.leaf} size={20} strokeWidth={2.5} /> },
  { id: 'diary', label: 'Diary', symbol: <PencilLine color={colors.leaf} size={20} strokeWidth={2.5} /> },
];

export function AppTabBar({ activeTab, onSelect }: { activeTab: MainTab; onSelect: (tab: MainTab) => void }) {
  return (
    <View accessibilityRole="tablist" style={styles.bar}>
      {tabs.map((tab) => {
        const selected = tab.id === activeTab;
        return (
          <Pressable
            key={tab.id}
            accessibilityLabel={tab.label}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => onSelect(tab.id)}
            style={({ pressed }) => [styles.tab, selected && styles.tabSelected, pressed && styles.pressed]}
          >
            <View style={styles.symbol}>{tab.symbol}</View>
            <Text style={[styles.label, selected && styles.selected]}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { backgroundColor: colors.paper, borderColor: '#E6E5DE', borderRadius: 30, borderWidth: StyleSheet.hairlineWidth, bottom: 14, elevation: 8, flexDirection: 'row', left: 20, minHeight: 64, padding: 6, position: 'absolute', right: 20, shadowColor: '#1C251E', shadowOpacity: 0.12, shadowOffset: { width: 0, height: 6 }, shadowRadius: 16 },
  tab: { alignItems: 'center', borderRadius: 22, flex: 1, gap: 2, justifyContent: 'center', minHeight: 48 },
  tabSelected: { backgroundColor: colors.accentWash },
  symbol: { alignItems: 'center', height: 22, justifyContent: 'center' },
  label: { color: colors.slate, fontSize: 16, fontWeight: '800' },
  selected: { color: colors.leaf },
  pressed: { opacity: 0.58 },
});
