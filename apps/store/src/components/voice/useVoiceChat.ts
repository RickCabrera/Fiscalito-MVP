/** useVoiceChat — Custom hook for voice chat state, message handling, API calls, and recording */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProfile } from '../../context/ProfileContext';
import { useAuth } from '../../context/AuthContext';
import { obtenerHistorial } from '../../services/declaracionesHistory';
import {
  startRecording, stopRecording, transcribeAudio,
  speakText, stopSpeaking,
  detectSilence, type ChatMessage,
} from '../../services/voiceChatService';
import { runAgentLoop } from '../../agent/agentLoop';

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking';

export interface BubbleMsg {
  role: 'user' | 'assistant';
  content: string;
}

// ── Helpers ──

function fmtMoney(n: number): string {
  return n.toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
}

// Whisper hallucinations: phrases it produces when there's no real speech (silence, noise)
const WHISPER_NOISE_PHRASES = new Set([
  '',
  'you',
  'thank you',
  'thanks for watching',
  'gracias por ver',
  'subtítulos realizados por la comunidad de amara.org',
  'subtítulos por la comunidad de amara.org',
]);

function isNoiseTranscription(text: string): boolean {
  const trimmed = text.trim();
  if (trimmed.length < 3) return true;
  return WHISPER_NOISE_PHRASES.has(trimmed.toLowerCase());
}

async function buildHistorialResumen(uid: string): Promise<string> {
  try {
    const records = await obtenerHistorial(uid, 3, 'predeclaracion');
    if (records.length === 0) return 'Sin historial aun.';
    return records
      .map((r) => {
        const isr = r.desglose?.isr_a_pagar ?? 0;
        const iva = r.desglose?.iva_a_pagar ?? 0;
        return `${r.periodo}: ISR ${fmtMoney(isr)}, IVA ${fmtMoney(iva)}`;
      })
      .join(' | ');
  } catch {
    return 'No se pudo cargar historial.';
  }
}

// ── Hook ──

export function useVoiceChat() {
  const { profile } = useProfile();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<BubbleMsg[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [voiceLoopActive, setVoiceLoopActive] = useState(false);
  const [historialResumen, setHistorialResumen] = useState('');
  const [ready, setReady] = useState(false);

  // Refs to avoid stale closures in the voice loop
  const loopActiveRef = useRef(false);
  const openRef = useRef(false);
  const chatHistoryRef = useRef<ChatMessage[]>([]);
  const profileRef = useRef(profile);
  const historialRef = useRef('');
  const uidRef = useRef<string | null>(user?.uid ?? null);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Sync refs
  useEffect(() => { profileRef.current = profile; }, [profile]);
  useEffect(() => { historialRef.current = historialResumen; }, [historialResumen]);
  useEffect(() => { chatHistoryRef.current = chatHistory; }, [chatHistory]);
  useEffect(() => { openRef.current = open; }, [open]);
  useEffect(() => { uidRef.current = user?.uid ?? null; }, [user?.uid]);

  // Auto-scroll messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  // Load context + welcome message on first open
  useEffect(() => {
    if (!open || ready) return;
    (async () => {
      const resumen = user?.uid ? await buildHistorialResumen(user.uid) : '';
      setHistorialResumen(resumen);
      const nombre = profile.nombre || 'contribuyente';
      const welcome = `Hola ${nombre}! Soy Fiscalito, tu asesor fiscal. Puedes escribirme o hablar conmigo. En que te ayudo hoy?`;
      setMessages([{ role: 'assistant', content: welcome }]);
      const hist: ChatMessage[] = [{ role: 'assistant', content: welcome }];
      setChatHistory(hist);
      chatHistoryRef.current = hist;
      setReady(true);
    })();
  }, [open, ready, user?.uid, profile.nombre]);

  // Process a user message (text) through the agent loop + optional TTS.
  // Las refs vivas (profileRef, historialRef, chatHistoryRef) se leen en el
  // llamado, no en el closure de React, para respetar el voice loop continuo.
  const processUserMessage = useCallback(async (text: string, speakResponse: boolean): Promise<void> => {
    setMessages((prev) => [...prev, { role: 'user', content: text }]);

    setVoiceState('processing');
    try {
      const { reply, newHistory } = await runAgentLoop({
        history: chatHistoryRef.current,
        userMessage: text,
        profile: profileRef.current,
        historialResumen: historialRef.current,
        navigate,
        uid: uidRef.current,
      });

      setMessages((prev) => [...prev, { role: 'assistant', content: reply }]);
      chatHistoryRef.current = newHistory;
      setChatHistory(newHistory);

      if (speakResponse) {
        setVoiceState('speaking');
        // TTS failure is non-critical: we already displayed the text response
        try { await speakText(reply); } catch (e) { console.error('[FiscalitoVoiceChat] TTS error:', e); }
      }
    } catch (e) {
      console.error('[FiscalitoVoiceChat] agentLoop error:', e);
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Lo siento, hubo un error. Intenta de nuevo.' }]);
    }
  }, [navigate]);

  // Continuous voice loop: listen -> transcribe -> LLM -> TTS -> repeat
  const runVoiceLoop = useCallback(async () => {
    while (loopActiveRef.current && openRef.current) {
      try {
        setVoiceState('listening');
        await startRecording();

        // Wait for 2s silence via VAD
        await new Promise<void>((resolve) => {
          vadCleanupRef.current = detectSilence(() => {
            vadCleanupRef.current?.();
            vadCleanupRef.current = null;
            resolve();
          }, 2000);
        });

        if (!loopActiveRef.current || !openRef.current) {
          try { await stopRecording(); } catch { /* recording may already be stopped */ }
          break;
        }

        const blob = await stopRecording();

        setVoiceState('processing');
        const text = await transcribeAudio(blob);
        if (!text || !loopActiveRef.current) continue;

        // Skip Whisper hallucinations from silence/noise — keep listening
        if (isNoiseTranscription(text)) {
          console.log('[FiscalitoVoiceChat] ignored noise transcription:', JSON.stringify(text));
          continue;
        }

        await processUserMessage(text, true);
      } catch (e) {
        console.error('[FiscalitoVoiceChat] voice loop error:', e);
        // Brief pause before retrying on transient errors (mic access, network)
        if (loopActiveRef.current) {
          await new Promise((r) => setTimeout(r, 500));
        }
      }
    }

    setVoiceState('idle');
  }, [processUserMessage]);

  // Toggle mic / interrupt TTS
  const handleMicClick = useCallback(() => {
    if (voiceState === 'speaking') {
      // Interrupt TTS — stopSpeaking resolves the speakText promise,
      // so the loop naturally continues to the next recording cycle
      stopSpeaking();
      return;
    }

    if (loopActiveRef.current) {
      loopActiveRef.current = false;
      setVoiceLoopActive(false);
      vadCleanupRef.current?.();
      vadCleanupRef.current = null;
      stopRecording().catch(() => { /* may not be recording */ });
      setVoiceState('idle');
    } else {
      loopActiveRef.current = true;
      setVoiceLoopActive(true);
      runVoiceLoop();
    }
  }, [voiceState, runVoiceLoop]);

  // Send text message (when voice loop is paused)
  const handleTextSend = useCallback(async () => {
    const msg = input.trim();
    if (!msg || voiceLoopActive) return;
    setInput('');
    await processUserMessage(msg, true);
    setVoiceState('idle');
  }, [input, voiceLoopActive, processUserMessage]);

  // Close panel and stop all audio activity
  const handleClose = useCallback(() => {
    loopActiveRef.current = false;
    setVoiceLoopActive(false);
    vadCleanupRef.current?.();
    vadCleanupRef.current = null;
    stopSpeaking();
    stopRecording().catch(() => { /* may not be recording */ });
    setVoiceState('idle');
    setOpen(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => () => {
    loopActiveRef.current = false;
    vadCleanupRef.current?.();
    stopSpeaking();
    stopRecording().catch(() => { /* may not be recording */ });
  }, []);

  const statusLabel = voiceState === 'listening' ? 'Escuchando...'
    : voiceState === 'processing' ? 'Procesando...'
    : voiceState === 'speaking' ? 'Hablando...'
    : null;

  return {
    open, setOpen,
    messages,
    input, setInput,
    voiceState,
    voiceLoopActive,
    statusLabel,
    scrollRef,
    handleMicClick,
    handleTextSend,
    handleClose,
  };
}
