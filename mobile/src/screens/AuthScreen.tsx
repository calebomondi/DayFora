import { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, View } from 'react-native';

import { PrimaryButton, TextButton, colors } from '../components/ui';
import { supabase } from '../lib/supabase';

export function AuthScreen() {
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!email.trim() || password.length < 8) return setMessage('Enter an email and a password with at least 8 characters.');
    setSubmitting(true); setMessage('');
    const result = mode === 'sign-in'
      ? await supabase.auth.signInWithPassword({ email: email.trim(), password })
      : await supabase.auth.signUp({ email: email.trim(), password });
    setSubmitting(false);
    if (result.error) return setMessage(result.error.message);
    if (mode === 'sign-up' && !result.data.session) setMessage('Check your email to confirm your account, then sign in.');
  }

  return <View style={styles.container}>
    <Text style={styles.wordmark}>DAYFORA</Text><Text style={styles.title}>{mode === 'sign-in' ? 'Welcome back.' : 'Make this space yours.'}</Text>
    <Text style={styles.copy}>Your diary, media, and progress stay private to your account.</Text>
    <View style={styles.form}>
      <TextInput accessibilityLabel="Email address" autoCapitalize="none" autoComplete="email" keyboardType="email-address" onChangeText={setEmail} placeholder="Email address" placeholderTextColor="#7A8988" style={styles.input} value={email} />
      <TextInput accessibilityLabel="Password" autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'} onChangeText={setPassword} placeholder="Password" placeholderTextColor="#7A8988" secureTextEntry style={styles.input} value={password} />
    </View>
    <PrimaryButton onPress={submit} tone="leaf">{submitting ? 'Working…' : mode === 'sign-in' ? 'Sign in' : 'Create account'}</PrimaryButton>
    {submitting ? <ActivityIndicator color={colors.leaf} style={styles.spinner} /> : null}
    {message ? <Text style={styles.message}>{message}</Text> : null}
    <TextButton onPress={() => { setMode(mode === 'sign-in' ? 'sign-up' : 'sign-in'); setMessage(''); }}>{mode === 'sign-in' ? 'New here? Create an account' : 'Already have an account? Sign in'}</TextButton>
  </View>;
}

const styles = StyleSheet.create({ container: { backgroundColor: colors.canvas, flex: 1, justifyContent: 'center', padding: 24 }, wordmark: { color: colors.leaf, fontSize: 13, fontWeight: '800', letterSpacing: 2, marginBottom: 18 }, title: { color: colors.ink, fontSize: 37, fontWeight: '700', letterSpacing: -1 }, copy: { color: colors.slate, fontSize: 16, lineHeight: 23, marginBottom: 28, marginTop: 12 }, form: { backgroundColor: colors.surface, borderRadius: 20, marginBottom: 16, overflow: 'hidden' }, input: { backgroundColor: colors.paper, borderBottomColor: colors.line, borderBottomWidth: StyleSheet.hairlineWidth, color: colors.ink, fontSize: 16, minHeight: 54, paddingHorizontal: 16 }, message: { color: colors.slate, lineHeight: 20, marginTop: 14 }, spinner: { marginTop: 12 } });
