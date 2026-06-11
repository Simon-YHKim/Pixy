# 5-Minute Smoke Test / 5분 스모크 테스트

The fastest way to confirm Pixy works on YOUR machine. Every step below was
rehearsed end to end on a fresh clone before each release; if a step fails
for you, the error text is exactly what we need to fix it.

가장 빠른 실기기 검증 경로입니다. 아래 모든 단계는 릴리즈 전에 신선한
클론에서 리허설을 마친 상태입니다. 실패하면 에러 원문이 곧 버그 리포트입니다.

## 0. Update & doctor / 업데이트와 환경 진단

```bash
git pull
python scripts/pixy_doctor.py
```

Expected: `Track 1 (pure LLM + image model): READY`. Track 2 only needs
Blender if you want the 3D route - the doctor prints the exact install
command for your platform if it is missing.

기대 결과: Track 1 READY. Track 2는 3D 경로를 쓸 때만 필요하며, 없으면
닥터가 플랫폼별 설치 명령을 알려줍니다.

## 1. P1 - one sprite, end to end / 스프라이트 하나, 끝까지

Generate any image (your image tool, an API key, or any png you have), then:

이미지를 하나 만들고(쓰시는 이미지 툴, API 키, 아무 png나):

```bash
python scripts/pixyfly.py YOUR_IMAGE.png --name my_first --out-dir out/
```

Expected: `VERDICT: SHIP` (or REVIEW with concrete suggestions). Outputs:
`out/my_first.pix` + `out/my_first.png`.

## 2. P2 - directional set to a game engine / 8방향 세트를 엔진으로

```bash
python scripts/init_spec.py --out robot.spec.json --preset game-character --name robot
python scripts/charset.py --spec robot.spec.json --character "a round robot" \
    --poses s,e,n,w --out-dir prompts/
# generate one image per printed prompt into raw/ as s_0.png, e_0.png, n_0.png, w_0.png
python scripts/frames_to_pixel.py raw/ --spec robot.spec.json --out-dir sheet/ \
    --directions s,e,n,w --frames 1 --name robot --export godot
```

Expected: `RESULT: PASS` and `sheet/robot.tres` - drop it next to
`robot_sheet.png` in a Godot project and point an AnimatedSprite2D at it.

## 3. P7 - 3D route (only if Blender) / 3D 경로 (Blender 있을 때만)

```bash
python scripts/blender_snippet.py --mode blockout \
    --parts "sphere,body,0 0 0.5,0.55,#2b9c4a;sphere,eyeL,-0.14 -0.3 0.62,0.07,#12143b;sphere,eyeR,0.14 -0.3 0.62,0.07,#12143b" \
    --directions s,e,n,w --frames 1 --out slime.py
blender --background --python slime.py        # or paste into the Scripting tab
python scripts/frames_to_pixel.py pixy_raw/ --spec robot.spec.json \
    --out-dir slime_sheet/ --directions s,e,n,w --frames 1 --name slime
```

Expected: `PIXY_RENDER_DONE` from Blender, then a conformed sheet.

## If anything fails / 실패하면

Run the suite and copy the full error text:

```bash
python scripts/tests/run_all.py
```

The suite passing while a step above fails means the gap is environmental
(paths, image tool, Blender version) - exactly the report that makes the
next fix possible. 스위트는 통과하는데 위 단계가 실패한다면 환경 차이가
원인이며, 그 에러 원문이 다음 수정의 재료가 됩니다.
