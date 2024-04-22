import React, { useEffect, useRef, useState } from 'react';
import './App.css';

function App() {
  const [caption, setCaption] = useState('');
  const videoRef = useRef(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    // カメラの映像を取得する
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(stream => {
        videoRef.current.srcObject = stream;
      })
      .catch(console.error);

    // 5秒ごとにキャプションを更新する
    intervalRef.current = setInterval(() => {
      generateCaption();
    }, 5000);

    // クリーンアップ関数
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      const tracks = videoRef.current.srcObject?.getTracks();
      tracks?.forEach(track => track.stop());
    };
  }, []);

  // キャプションを生成する関数
  const generateCaption = async () => {
    if (!videoRef.current) return;

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const imageBlob = await new Promise(res => canvas.toBlob(res));

    const formData = new FormData();
    formData.append('file', imageBlob, 'capture.jpg');

    // キャプション生成エンドポイントにPOSTリクエストを送信
    fetch('http://localhost:8080/gencap/en', { // または '/gencap/ja' に変更して日本語のキャプションを生成
      method: 'POST',
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        setCaption(data.caption);
      })
      .catch(console.error);
  };

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
