"""
ナレーション音声生成スクリプト（VOICEVOXエンジン）

使い方:
  python generate_tts.py --text "テキスト" --voicevox-id 10 --output /path/to/output.wav

※ VOICEVOXアプリを起動しておく必要があります（localhost:50021）
"""
import argparse
import urllib.request
import urllib.parse
import json

VOICEVOX_URL = "http://localhost:50021"


def generate_voicevox(text, speaker_id, output_path, speed=1.0):
    query_url = f"{VOICEVOX_URL}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker_id}"
    req = urllib.request.Request(query_url, method="POST")
    with urllib.request.urlopen(req) as res:
        audio_query = json.loads(res.read())

    audio_query["speedScale"] = speed

    synth_url = f"{VOICEVOX_URL}/synthesis?speaker={speaker_id}"
    body = json.dumps(audio_query).encode("utf-8")
    req = urllib.request.Request(synth_url, data=body, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as res:
        wav_data = res.read()

    with open(output_path, "wb") as f:
        f.write(wav_data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="読み上げるテキスト")
    parser.add_argument("--voicevox-id", type=int, required=True, help="話者ID 例: 10")
    parser.add_argument("--output", required=True, help="出力wavファイルパス")
    parser.add_argument("--speed", type=float, default=1.0, help="話速 例: 0.8=ゆっくり, 1.0=普通, 1.2=早口")
    args = parser.parse_args()

    print(f"モード: VOICEVOX / 話者ID: {args.voicevox_id} / 話速: {args.speed}")
    print(f"テキスト: {args.text}")
    print("音声を生成中...")
    generate_voicevox(args.text, args.voicevox_id, args.output, args.speed)
    print(f"完了: {args.output}")


if __name__ == "__main__":
    main()
