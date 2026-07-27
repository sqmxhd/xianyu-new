import {
  LoadingOutlined,
  PauseCircleFilled,
  PlayCircleFilled,
  WarningOutlined
} from "@ant-design/icons";
import { Button, Tooltip, Typography } from "antd";
import { useEffect, useRef, useState } from "react";

import { getMessageAudio } from "../api";

interface VoiceMessagePlayerProps {
  accountId: string;
  conversationId: string;
  messagePk: string;
  label?: string | null;
}

function labelDuration(label?: string | null): number | null {
  const matched = label?.match(/(\d+)\s*秒/);
  return matched ? Number(matched[1]) : null;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) {
    return "语音";
  }
  const total = Math.max(0, Math.round(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function VoiceMessagePlayer({
  accountId,
  conversationId,
  messagePk,
  label
}: VoiceMessagePlayerProps) {
  const contextRef = useRef<AudioContext | null>(null);
  const bufferRef = useRef<AudioBuffer | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const mountedRef = useRef(true);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(() => labelDuration(label));

  const stop = () => {
    const source = sourceRef.current;
    sourceRef.current = null;
    if (source) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        // The source may already have ended.
      }
      source.disconnect();
    }
    setPlaying(false);
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const source = sourceRef.current;
      sourceRef.current = null;
      if (source) {
        source.onended = null;
        try {
          source.stop();
        } catch {
          // The source may already have ended.
        }
        source.disconnect();
      }
      const context = contextRef.current;
      contextRef.current = null;
      if (context) {
        void context.close();
      }
    };
  }, []);

  const play = async () => {
    if (playing) {
      stop();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const context = contextRef.current ?? new AudioContext();
      contextRef.current = context;
      await context.resume();

      let audioBuffer = bufferRef.current;
      if (!audioBuffer) {
        const blob = await getMessageAudio(accountId, conversationId, messagePk);
        const { default: decodeAmr } = await import("@audio/decode-amr");
        const decoded = await decodeAmr(await blob.arrayBuffer());
        if (!decoded.channelData.length || !decoded.channelData[0]?.length) {
          throw new Error("语音内容为空");
        }
        audioBuffer = context.createBuffer(
          decoded.channelData.length,
          decoded.channelData[0].length,
          decoded.sampleRate
        );
        decoded.channelData.forEach((channel, index) => {
          audioBuffer?.getChannelData(index).set(channel);
        });
        bufferRef.current = audioBuffer;
        if (mountedRef.current) {
          setDuration(audioBuffer.duration);
        }
      }

      stop();
      const source = context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(context.destination);
      source.onended = () => {
        if (sourceRef.current !== source) {
          return;
        }
        sourceRef.current = null;
        source.disconnect();
        if (mountedRef.current) {
          setPlaying(false);
        }
      };
      sourceRef.current = source;
      source.start();
      if (mountedRef.current) {
        setPlaying(true);
      }
    } catch (caught) {
      if (mountedRef.current) {
        setError(caught instanceof Error ? caught.message : "语音加载失败");
        setPlaying(false);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  };

  const icon = loading ? (
    <LoadingOutlined />
  ) : playing ? (
    <PauseCircleFilled />
  ) : (
    <PlayCircleFilled />
  );

  return (
    <div className="voice-message-player">
      <Button
        className="voice-message-play"
        type="text"
        icon={icon}
        disabled={loading}
        aria-label={playing ? "停止播放语音" : "播放语音"}
        onClick={() => void play()}
      />
      <Typography.Text>{playing ? "播放中" : formatDuration(duration)}</Typography.Text>
      {error ? (
        <Tooltip title={error}>
          <WarningOutlined className="voice-message-error" aria-label={error} />
        </Tooltip>
      ) : null}
    </div>
  );
}
