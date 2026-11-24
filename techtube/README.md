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

## 1) التثبيت على Windows خطوة بخطوة

تحتاج: Windows 10 أو 11، وحوالي **15GB** مساحة فارغة، واتصال إنترنت للتحميل مرة واحدة فقط.
المدة: حوالي ساعة، وأغلبها انتظار التحميل.

### الخطوة 1: تحميل الأداة
1. حمّل الملف المضغوط:
   https://github.com/abdelmoula2000/Almoo/archive/refs/heads/ccr-b96dd09f-vct00g.zip
   إذا كان المستودع خاصاً، سجّل دخولك إلى GitHub في المتصفح أولاً.
2. فك الضغط في مكان بسيط، مثلاً `C:\TechTube`.
3. المجلد المهم هو `techtube` داخل المجلد الذي فككته.

### الخطوة 2: Python 3.11
1. ادخل إلى https://www.python.org/downloads/release/python-3119/ وحمّل **Windows installer (64-bit)**.
2. شغّل المثبّت واضغط **Install Now**.
   - إذا كان عندك إصدار أحدث مثبت (3.12 أو 3.13 أو 3.14)، **لا تحذفه**. الإصداران يعيشان معاً بدون مشاكل.
   - مربع «Add python.exe to PATH» غير ضروري هنا، لأننا سنستخدم الأمر `py`.
3. افتح PowerShell (ابحث عنه في قائمة ابدأ) واكتب:
   ```powershell
   py -3.11 --version
   ```
   يجب أن يظهر `Python 3.11.9`.

لماذا 3.11 بالذات؟ لأن Kokoro (الصوت) يعمل فقط مع Python من 3.10 إلى 3.12. الأمر `py -3.11` يختار هذا الإصدار، حتى لو كان الإصدار الافتراضي عندك أحدث.

> **مشكلة شائعة:** إذا فتح الأمر متجر Microsoft بدل ظهور الرقم: افتح **الإعدادات ← التطبيقات ← إعدادات التطبيقات المتقدمة ← أسماء الأوامر المستعارة للتطبيقات (App execution aliases)**، وأطفئ `python.exe` و`python3.exe`، ثم أعد فتح PowerShell.

### الخطوة 3: ffmpeg (صناعة الفيديو)
1. في PowerShell:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   وافق على أي سؤال بكتابة `Y`.
2. **أغلق PowerShell وافتحه من جديد** (ضروري)، ثم تأكد:
   ```powershell
   ffmpeg -version
   ```

### الخطوة 4: Ollama (الذكاء الاصطناعي الذي يكتب السكريبت)
1. حمّل `OllamaSetup.exe` من https://ollama.com/download وثبّته. بعد التثبيت يعمل في الخلفية، وتظهر أيقونته بجانب الساعة.
2. نزّل النموذج (حوالي 2GB):
   ```powershell
   ollama pull llama3.2:3b
   ```
3. جرّبه:
   ```powershell
   ollama run llama3.2:3b "Say hello in one sentence"
   ```
   إذا ردّ عليك بجملة، فهو يعمل. Ollama يستخدم كرت الشاشة تلقائياً.

### الخطوة 5: eSpeak NG (يساعد الصوت في نطق الكلمات الصعبة)
1. ادخل إلى https://github.com/espeak-ng/espeak-ng/releases
2. حمّل ملف `.msi` الخاص بـ X64 من آخر إصدار، وثبّته بالإعدادات الافتراضية.

### الخطوة 6: مكتبات الأداة
1. افتح مجلد `techtube` في مستكشف الملفات، واضغط على شريط العنوان في الأعلى، واكتب `powershell` ثم Enter. ستفتح نافذة PowerShell داخل المجلد.
2. أنشئ بيئة خاصة بالأداة وفعّلها:
   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   python --version
   ```
   يجب أن يظهر `(.venv)` في بداية السطر، و`Python 3.11.9`. داخل هذه البيئة، الأمر `python` يعني دائماً 3.11.
   > إذا ظهر خطأ **running scripts is disabled**، نفّذ هذا الأمر مرة واحدة، واكتب `Y`، ثم أعد أمر التفعيل:
   > ```powershell
   > Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   > ```
3. ثبّت المكتبات (حوالي 2 إلى 3GB، وقد تأخذ من 10 إلى 30 دقيقة):
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```

### الخطوة 7: الإعدادات
1. انسخ الملف `config.example.json` وسمِّ النسخة `config.json`.
2. افتحه بالمفكرة (Notepad)، وغيّر `"Fix It Fast"` إلى اسم قناتك، ثم احفظ.

### الخطوة 8: التجربة الأولى
في نفس نافذة PowerShell (وفيها `(.venv)`):
```powershell
python tt.py script --from-file examples/laptop-overheating.md
python tt.py all laptop-overheating
```
- **في أول مرة:** سيحمّل نموذج الصوت ونموذج الترجمة (بضع مئات من الميغابايت)، ثم يصنع الفيديو.
- **النتيجة:** في `projects\laptop-overheating\`:
  - `final.mp4`
  - `shorts\`
  - `youtube.txt`
  - `check.md`

ثم جرّب سكريبتاً يكتبه Ollama:
```powershell
python tt.py script "wifi keeps disconnecting" --context "Windows 11"
```

### كل مرة تفتح فيها الجهاز
افتح PowerShell داخل مجلد `techtube` (كما في الخطوة 6)، ثم:
```powershell
.venv\Scripts\activate
```
وبعدها استخدم الأوامر. Ollama يعمل وحده في الخلفية.

### اختياري: تسريع الريندر بكرت NVIDIA
في `config.json` غيّر `"encoder": "libx264"` إلى `"encoder": "h264_nvenc"`.
إذا ظهر خطأ عند الريندر، أرجعها كما كانت. الترجمة (Whisper) تعمل على المعالج افتراضياً لأنها تحتاج مكتبات NVIDIA إضافية على Windows.

> على Mac أو Linux نفس الفكرة:
> - ffmpeg: `brew install ffmpeg` أو `sudo apt install ffmpeg`
> - eSpeak NG: `brew install espeak-ng` أو `sudo apt install espeak-ng`
> - تفعيل البيئة: `source .venv/bin/activate`

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
