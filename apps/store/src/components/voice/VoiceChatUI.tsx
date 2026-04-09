/** VoiceChatUI — Visual rendering for the Fiscalito voice chat panel */

import React from 'react';
import { Mic, MicOff, Send, X, Volume2, Loader } from 'lucide-react';
import type { VoiceState, BubbleMsg } from './useVoiceChat';

interface VoiceChatUIProps {
  messages: BubbleMsg[];
  input: string;
  voiceState: VoiceState;
  voiceLoopActive: boolean;
  statusLabel: string | null;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  onInputChange: (value: string) => void;
  onMicClick: () => void;
  onTextSend: () => void;
  onClose: () => void;
}

export default function VoiceChatUI({
  messages, input, voiceState, voiceLoopActive,
  statusLabel, scrollRef,
  onInputChange, onMicClick, onTextSend, onClose,
}: VoiceChatUIProps) {
  return (
    <>
      <div onClick={onClose} style={backdropStyle} />

      <div style={panelStyle}>
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
            <div style={avatarStyle}>F</div>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>Fiscalito IA</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }} />
                En linea
              </div>
            </div>
          </div>
          <button onClick={onClose} style={iconBtnStyle}><X size={18} /></button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} style={messagesAreaStyle}>
          {messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 10 }}>
              <div style={m.role === 'user' ? bubbleUserStyle : bubbleAssistantStyle}>
                {m.content}
              </div>
            </div>
          ))}
        </div>

        {/* Status bar */}
        {statusLabel && (
          <div style={statusBarStyle}>
            {voiceState === 'listening' && <MicOff size={14} color="var(--danger)" />}
            {voiceState === 'processing' && <Loader size={14} className="spin" />}
            {voiceState === 'speaking' && <Volume2 size={14} color="var(--teal-light)" className="pulse" />}
            <span>{statusLabel}</span>
          </div>
        )}

        {/* Input bar */}
        <div style={inputBarStyle}>
          <button onClick={onMicClick} disabled={voiceState === 'processing'}
            style={{
              ...micBtnStyle,
              background: voiceLoopActive ? 'rgba(231,76,60,0.15)'
                : voiceState === 'speaking' ? 'rgba(110,159,160,0.15)' : 'transparent',
              color: voiceLoopActive ? 'var(--danger)'
                : voiceState === 'speaking' ? 'var(--teal-light)' : 'var(--text-secondary)',
              animation: voiceLoopActive && voiceState === 'listening' ? 'pulse 1.5s infinite' : 'none',
            }}>
            {voiceState === 'speaking' ? <Volume2 size={20} />
              : voiceLoopActive ? <MicOff size={20} />
              : <Mic size={20} />}
          </button>
          <input
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onTextSend(); } }}
            placeholder={voiceLoopActive ? 'Voz activa — pausa para escribir' : 'Escribe un mensaje...'}
            disabled={voiceLoopActive || voiceState === 'processing'}
            style={textInputStyle}
          />
          <button onClick={onTextSend}
            disabled={!input.trim() || voiceLoopActive || voiceState !== 'idle'}
            style={{ ...sendBtnStyle, opacity: input.trim() && !voiceLoopActive && voiceState === 'idle' ? 1 : 0.4 }}>
            <Send size={18} />
          </button>
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
        .pulse { animation: pulse 1.2s ease-in-out infinite; }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </>
  );
}

// ── Inline Styles ──

const backdropStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 9000, background: 'rgba(0,0,0,0.3)',
};

const panelStyle: React.CSSProperties = {
  position: 'fixed', bottom: 24, right: 64, zIndex: 9001,
  width: 380, height: 520,
  background: 'var(--bg-card)', border: '1px solid var(--purple)',
  borderRadius: 16, display: 'flex', flexDirection: 'column',
  boxShadow: 'var(--shadow-lg)', overflow: 'hidden',
};

const headerStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '12px 14px', borderBottom: '1px solid var(--border)',
  background: 'var(--bg-surface)',
};

const avatarStyle: React.CSSProperties = {
  width: 34, height: 34, borderRadius: '50%',
  background: 'var(--accent-gradient)', color: '#fff',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontWeight: 700, fontSize: '0.95rem',
};

const iconBtnStyle: React.CSSProperties = {
  background: 'none', border: 'none', color: 'var(--text-muted)',
  cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center',
};

const messagesAreaStyle: React.CSSProperties = {
  flex: 1, overflowY: 'auto', padding: '14px 12px',
  display: 'flex', flexDirection: 'column',
};

const bubbleBase: React.CSSProperties = {
  maxWidth: '78%', padding: '10px 14px', borderRadius: 14,
  fontSize: '0.85rem', lineHeight: 1.55, wordBreak: 'break-word',
};

const bubbleUserStyle: React.CSSProperties = {
  ...bubbleBase, background: 'var(--purple)', color: 'var(--text-on-accent)',
  borderBottomRightRadius: 4,
};

const bubbleAssistantStyle: React.CSSProperties = {
  ...bubbleBase, background: 'var(--bg-surface)', color: 'var(--text-primary)',
  border: '1px solid var(--border)', borderBottomLeftRadius: 4,
};

const statusBarStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '6px 14px', fontSize: '0.75rem', color: 'var(--text-muted)',
  borderTop: '1px solid var(--border)',
};

const inputBarStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '10px 10px', borderTop: '1px solid var(--border)',
  background: 'var(--bg-surface)',
};

const micBtnStyle: React.CSSProperties = {
  width: 38, height: 38, borderRadius: '50%',
  border: '1px solid var(--border)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
  flexShrink: 0, transition: 'all 0.2s',
};

const textInputStyle: React.CSSProperties = {
  flex: 1, background: 'var(--bg-input)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-full)', padding: '8px 14px',
  color: 'var(--text-primary)', fontSize: '0.85rem',
};

const sendBtnStyle: React.CSSProperties = {
  width: 38, height: 38, borderRadius: '50%',
  background: 'var(--accent-gradient)', color: '#fff',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  border: 'none', cursor: 'pointer', flexShrink: 0, transition: 'opacity 0.2s',
};
