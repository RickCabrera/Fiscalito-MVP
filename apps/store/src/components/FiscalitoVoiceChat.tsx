/** FiscalitoVoiceChat — Floating button + voice chat panel (thin wrapper) */

import React from 'react';
import { Mic } from 'lucide-react';
import { useVoiceChat } from './voice/useVoiceChat';
import VoiceChatUI from './voice/VoiceChatUI';

export default function FiscalitoVoiceChat() {
  const {
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
  } = useVoiceChat();

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} aria-label="Abrir chat de voz" style={fabStyle}>
        <Mic size={24} />
      </button>
    );
  }

  return (
    <VoiceChatUI
      messages={messages}
      input={input}
      voiceState={voiceState}
      voiceLoopActive={voiceLoopActive}
      statusLabel={statusLabel}
      scrollRef={scrollRef}
      onInputChange={setInput}
      onMicClick={handleMicClick}
      onTextSend={handleTextSend}
      onClose={handleClose}
    />
  );
}

const fabStyle: React.CSSProperties = {
  position: 'fixed', bottom: 24, right: 24, zIndex: 9000,
  width: 56, height: 56, borderRadius: '50%',
  background: 'var(--accent-gradient)', color: '#fff',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  boxShadow: 'var(--shadow-glow-purple)', border: 'none', cursor: 'pointer',
  transition: 'transform 0.2s, box-shadow 0.2s',
};
