import RFB from "@novnc/novnc";
import { FullscreenExitOutlined, FullscreenOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import { useEffect, useRef, useState } from "react";

type Props = {
  websocketUrl: string;
  onConnected?: () => void;
  onDisconnected?: (clean: boolean) => void;
  onActivity?: () => void;
};

export function IMVerificationViewer({
  websocketUrl,
  onConnected,
  onDisconnected,
  onActivity
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);
  const onActivityRef = useRef(onActivity);
  onConnectedRef.current = onConnected;
  onDisconnectedRef.current = onDisconnected;
  onActivityRef.current = onActivity;

  useEffect(() => {
    const target = viewportRef.current;
    if (!target || !websocketUrl) {
      return;
    }
    const rfb = new RFB(target, websocketUrl);
    rfb.scaleViewport = true;
    rfb.resizeSession = false;
    rfb.viewOnly = false;
    rfb.focusOnClick = true;
    rfb.addEventListener("connect", () => onConnectedRef.current?.());
    rfb.addEventListener("disconnect", (event) => {
      const clean = Boolean((event as CustomEvent<{ clean?: boolean }>).detail?.clean);
      onDisconnectedRef.current?.(clean);
    });
    const reportActivity = () => onActivityRef.current?.();
    target.addEventListener("pointerdown", reportActivity, true);
    target.addEventListener("pointermove", reportActivity, true);
    target.addEventListener("keydown", reportActivity, true);
    target.addEventListener("wheel", reportActivity, { capture: true, passive: true });
    target.addEventListener("touchstart", reportActivity, { capture: true, passive: true });
    return () => {
      target.removeEventListener("pointerdown", reportActivity, true);
      target.removeEventListener("pointermove", reportActivity, true);
      target.removeEventListener("keydown", reportActivity, true);
      target.removeEventListener("wheel", reportActivity, true);
      target.removeEventListener("touchstart", reportActivity, true);
      rfb.disconnect();
    };
  }, [websocketUrl]);

  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === containerRef.current);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  async function toggleFullscreen() {
    const container = containerRef.current;
    if (!container) return;
    if (document.fullscreenElement === container) {
      await document.exitFullscreen();
    } else {
      await container.requestFullscreen();
    }
  }

  return (
    <div ref={containerRef} className="im-verification-viewer">
      <div ref={viewportRef} className="im-verification-viewer-viewport" />
      <Tooltip title={fullscreen ? "退出全屏" : "全屏查看"}>
        <Button
          className="im-verification-fullscreen"
          type="text"
          icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          aria-label={fullscreen ? "退出 VNC 全屏" : "VNC 全屏查看"}
          onClick={() => void toggleFullscreen()}
        />
      </Tooltip>
    </div>
  );
}
