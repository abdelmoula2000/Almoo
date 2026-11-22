# TechTube — صناعة فيديوهات يوتيوب تقنية من «مشكلة وحلها»

أداة مجانية تعمل على جهازك بالكامل. تعطيها مشكلة تقنية مثل `laptop overheating`، فتصنع لك:

| الناتج | الملف |
|---|---|
| سكريبت إنجليزي تراجعه وتعدّله | `script.md` |
| فيديو طويل 1920×1080 بشرائح متحركة وتعليق صوتي وترجمة | `final.mp4` |
| شورتس عمودية 1080×1920 | `shorts/short_01.mp4` … |
| عناوين ووصف وكلمات مفتاحية وفصول | `youtube.txt` |
| فحص سياسات يوتيوب قبل النشر (بالعربية) | `check.md` |
| أفكار فيديوهات من المواضيع الرائجة | `projects/_trends/trends-<التاريخ>.md` |

لا اشتراكات ولا API مدفوع. الذكاء الاصطناعي يعمل محلياً عبر **Ollama** و**Kokoro** و**Whisper**.

---

## 1) التثبيت (Windows)

1. **Python 3.11**: من [python.org](https://www.python.org/downloads/release/python-3119/). عند التثبيت فعّل خيار **Add Python to PATH**.
   - استخدم 3.11 أو 3.12، لأن Kokoro يعتمد على PyTorch الذي قد لا يدعم أحدث إصدارات Python.
2. **ffmpeg**: افتح PowerShell واكتب:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   ثم أغلق PowerShell وافتحه من جديد، وتأكد بالأمر `ffmpeg -version`.
3. **Ollama**: حمّله من [ollama.com](https://ollama.com/download) وثبّته، ثم نزّل النموذج:
   ```powershell
   ollama pull llama3.2:3b
   ```
   مناسب لكرت شاشة 4GB. بديل جيد: `qwen2.5:3b`. وإذا أردت جودة أعلى (أبطأ): `qwen2.5:7b`.
4. **eSpeak NG** (يحتاجه Kokoro لنطق بعض الكلمات): المثبّت من
   [صفحة الإصدارات](https://github.com/espeak-ng/espeak-ng/releases) (ملف `.msi`).
5. **مكتبات Python**: داخل مجلد `techtube`:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   - لتسريع الترجمة باستعمال كرت الشاشة NVIDIA، ثبّت بعدها PyTorch بنسخة CUDA من
     [pytorch.org](https://pytorch.org/get-started/locally/). وبدونها تعمل الأداة على المعالج، لكنها أبطأ.
6. **الإعدادات**: انسخ `config.example.json` باسم `config.json`، وغيّر اسم قناتك في `channel_name`.

> على Mac أو Linux نفس الخطوات: ffmpeg عبر `brew install ffmpeg` أو `sudo apt install ffmpeg`، وeSpeak عبر `brew install espeak-ng` أو `sudo apt install espeak-ng`.

---

## 2) العمل اليومي (5 خطوات)

```powershell
# 1. اختر موضوعاً من المواضيع الرائجة
python tt.py trends

# 2. اكتب السكريبت بالذكاء الاصطناعي
python tt.py script "laptop overheating" --context "Windows 11" --minutes 7

# 3. افتح projects\laptop-overheating\script.md وراجعه:
#    صحّح أي خطأ، وأضف نصيحة أو تجربة منك. (هذا مهم جداً لسياسة يوتيوب)
#    اختياري: ضع لقطات شاشة في projects\laptop-overheating\shots\

# 4. معاينة سريعة لشكل الشرائح (ثوانٍ)
python tt.py preview laptop-overheating --vertical

# 5. كل شيء دفعة واحدة: صوت ← فيديو ← شورتس ← بيانات يوتيوب ← فحص
python tt.py all laptop-overheating
```

بعدها افتح مجلد المشروع، واقرأ `check.md` قبل النشر.

### الأوامر بالتفصيل

| الأمر | ماذا يفعل |
|---|---|
| `trends [--seed "windows 11,android"] [--deep]` | يجمع المواضيع الرائجة من اقتراحات يوتيوب وReddit وHacker News، ثم يرتّبها الذكاء الاصطناعي |
| `script "<المشكلة>" [--context ...] [--minutes 7]` | يكتب `script.md` (ويحفظ نسخة أصلية باسم `script.draft.md` للمقارنة) |
| `script --from-file my.md` | ينشئ مشروعاً من سكريبت كتبته بنفسك، بدون ذكاء اصطناعي |
| `preview <مشروع> [--vertical] [--section 3]` | صور PNG لكل شريحة داخل `build/preview/` |
| `voice <مشروع> [--engine auto/kokoro/own] [--voice am_michael]` | التعليق الصوتي |
| `build <مشروع> [--theme ocean] [--music song.mp3]` | الفيديو الطويل `final.mp4` |
| `shorts <مشروع> [--sections 2,4]` | الشورتس |
| `meta <مشروع>` | يكتب `youtube.txt` |
| `check <مشروع> [--llm]` | يكتب `check.md`، والخيار `--llm` يطلب من الذكاء الاصطناعي أيضاً تحديد المعلومات المشكوك فيها |
| `themes` | قائمة الأشكال المتاحة |

---

## 3) صيغة السكريبت

```markdown
# Laptop Overheating? 4 Easy Fixes That Actually Work
problem: laptop overheating

## Why your laptop gets so hot
[visual: title]
Is your laptop getting hot...

## Step 1: Find what is using your CPU
[visual: terminal]
[code: Get-Process | Sort-Object CPU -Descending | Select-Object -First 5]
First, let's find out...

## Step 2: Give it room to breathe
[visual: steps]
[bullets: Use a hard, flat surface; Keep side vents uncovered; Lift the back slightly]
[short: yes]
This one sounds simple...

## Step 3: Switch to a balanced power mode
[visual: shot: 01.png focus=0.6,0.4 zoom=1.8 box=0.3,0.3,0.6,0.1]
Open Settings...
```

| السطر | المعنى |
|---|---|
| `## ...` | بداية قسم، وعنوانه يظهر على الشاشة. اكتب `Step 1: ...` ليظهر رقم الخطوة |
| `[visual: title]` | شريحة العنوان |
| `[visual: steps]` | نقاط تظهر واحدة تلو الأخرى (من `[bullets: أ; ب; ج]`) |
| `[visual: terminal]` | نافذة أوامر تُكتب حرفاً حرفاً (من `[code: ...]`) |
| `[visual: tip]` | نصيحة، أو تحذير إذا ذكرت backup أو careful |
| `[visual: outro]` | الخاتمة وزر الاشتراك |
| `[visual: shot: 01.png ...]` | لقطة شاشة من مجلد `shots/` |
| `[short: yes]` | هذا القسم يتحوّل إلى شورت |

خيارات لقطة الشاشة (`shot`):
- `focus=x,y`: نقطة التكبير، من 0 إلى 1.
- `zoom`: مقدار التكبير.
- `box=x,y,عرض,ارتفاع`: إطار ملوّن حول المكان المهم، بنسب من 0 إلى 1 من حجم الصورة.

وأي نص آخر داخل القسم هو كلام المعلّق.

### صوتك بدل الصوت الآلي

سجّل كل قسم في ملف داخل مجلد `myvoice/` بأسماء مرقّمة: `01.wav` و`02.m4a` وهكذا. ثم:
```powershell
python tt.py voice laptop-overheating --engine own
```
صوتك الحقيقي يزيد الثقة والأصالة كثيراً.

**أصوات Kokoro الإنجليزية:** `af_heart` (افتراضي)، `af_bella`، `am_michael`، `am_fenrir`، `bf_emma`، `bm_george`.

### الموسيقى

استخدم فقط موسيقى مسموحاً بها، مثل [مكتبة يوتيوب الصوتية](https://studio.youtube.com) (Audio Library):
```powershell
python tt.py build laptop-overheating --music music\calm.mp3
```
وسجّل مصدرها في `assets.json`، فأمر `check` ينشئ القالب لك.

---

## 4) لماذا هذه الأداة آمنة مع سياسة يوتيوب؟

منذ يوليو 2025 يوقف يوتيوب الأرباح عن «المحتوى غير الأصيل»، أي المحتوى المُنتَج بالجملة والمتكرر. الأداة مصممة لتجنّب ذلك:

| ميزة الأداة | ما تحميك منه |
|---|---|
| شكل مختلف (Theme) لكل فيديو تلقائياً | القوالب المكررة |
| `check` يقارن نصك بفيديوهاتك السابقة | تكرار نفس المحتوى |
| `check` يقارن السكريبت بالمسودة الآلية، ويطلب منك إضافة لمستك | نشر نص الذكاء الاصطناعي كما هو |
| فحص العنوان | المبالغة (Clickbait)، والرقم الذي لا يطابق عدد الخطوات |
| فحص الخطوات الخطيرة (Registry، BIOS…) | غياب التحذير المناسب |
| فحص `assets.json` | صور أو موسيقى بلا ترخيص |

**لكن تبقى مسؤوليتك:** جرّب الحل بنفسك، وأضف لقطات من جهازك، ولا تنشر أكثر مما تستطيع مراجعته.

---

## 5) مشاكل شائعة

| المشكلة | الحل |
|---|---|
| `Ollama is not running` | افتح تطبيق Ollama، أو نفّذ `ollama serve` |
| `Model ... not found` | `ollama pull llama3.2:3b` |
| `'ffmpeg' is not installed` | ثبّت ffmpeg وأعد فتح PowerShell |
| السكريبت ضعيف أو ناقص | جرّب `--model qwen2.5:7b`، أو أعد الأمر مع `--force` |
| Kokoro يتوقف عند أول تشغيل بسبب spaCy | `python -m spacy download en_core_web_sm` |
| Kokoro ينطق كلمة بشكل خاطئ | اكتبها في السكريبت كما تُنطق، أو ثبّت eSpeak NG |
| الترجمة غير متزامنة | ثبّت `faster-whisper`، أو استخدم `--captions whisper` |
| الريندر بطيء | في `config.json` جرّب `"encoder": "h264_nvenc"` لاستخدام كرت NVIDIA |

## للمطورين

```bash
pip install pytest
python -m pytest -q
```
