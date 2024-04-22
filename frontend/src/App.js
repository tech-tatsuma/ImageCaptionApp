import React, { useEffect, useRef, useState } from 'react';
import './App.css';

function App() {
  const [caption, setCaption] = useState('');
  const videoRef = useRef(null);
  const peerConnection = useRef(null);
  const dataChannel = useRef(null);

  useEffect(() => {
    async function setupWebRTC() {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      videoRef.current.srcObject = stream;

      // RTCPeerConnection を初期化
      peerConnection.current = new RTCPeerConnection();

      // メディアトラックを追加
      stream.getTracks().forEach(track => peerConnection.current.addTrack(track, stream));

      // データチャネルの設定
      dataChannel.current = peerConnection.current.createDataChannel("captionChannel");
      dataChannel.current.onmessage = (event) => {
        setCaption(event.data);
      };

      // オファーを作成して送信
      const offer = await peerConnection.current.createOffer();
      await peerConnection.current.setLocalDescription(offer);

      const response = await fetch('http://localhost:8080/offer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          sdp: peerConnection.current.localDescription.sdp,
          type: peerConnection.current.localDescription.type
        })
      });

      const { sdp, type } = await response.json();
      await peerConnection.current.setRemoteDescription(new RTCSessionDescription({ sdp, type }));
    }

    setupWebRTC();

    return () => {
      // コンポーネントアンマウント時のクリーンアップ
      peerConnection.current?.close();
    };
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1 className="App-title">Img Caption Generator</h1>
        <video ref={videoRef} autoPlay className="App-video"></video>
        <textarea className="App-caption" value={caption} placeholder="Caption will appear here..." readOnly></textarea>
      </header>
    </div>
  );
}

export default App;
