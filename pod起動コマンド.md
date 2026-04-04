# Pod起動コマンド

## 初回セットアップ（新規Pod / Volume なし）
```bash
wget -qO- https://raw.githubusercontent.com/keeeeeNinja/OssMovieAIz/master/setup_comfyui.sh | bash
```

## Pod再起動時（Network Volume付き / 既存環境あり）
```bash
wget -qO- https://raw.githubusercontent.com/keeeeeNinja/OssMovieAIz/master/setup_comfyui.sh | bash -s -- --restart
```

> **なぜ再起動時も実行が必要？**
> Network VolumeにはComfyUIコード・モデル・カスタムノードは永続化されるが、
> pipパッケージ（gguf, sageattention等）はPodのシステム側にあるため再起動でリセットされる。
> `--restart` はpip依存の再インストール + ComfyUI起動だけを行う（約1-2分）。
