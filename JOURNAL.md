# Project journal · سجل المشروع

**Group · المجموعة:** نواف الزميع · عبدالله الوهيبي · حمد الكعيد
**AI coding agent · الوكيل:** Claude (Opus 5.5) in the Claude app; we ran every command ourselves in the Terminal.
**Track · المسار:** fraud (built on the workshop's fraud-scoring labs)
**Repository · المستودع:** https://github.com/4onn/fraud-service

> هذه المداخل كتب الوكيل مسودتها مما حدث فعلًا في الجلسات، وراجعناها وعدّلناها بأنفسنا.

---

## Stage 0: Track and model · المسار والنموذج

**What we asked the agent · ما طلبناه من الوكيل**
اشرح لي النموذج بكلمات بسيطة: وش يدخل، وش يطلع، كم دقته، ومتى يغلط. وقِس ذلك بأرقام حقيقية.

**What it built · ما بناه**
- `scripts/model_card.py`: يمرر الـ 5,000 عملية عبر كود الخدمة الحقيقي ويقارن القرارات بالإجابات الصحيحة.
- `MODEL_CARD.md`: النتيجة، مولّدة من السكربت.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- المدخل: عملية بطاقة واحدة (المبلغ بالريال، القناة، نوع التاجر، رقم العميل، الوقت).
  النموذج يرى 5 features فقط: `amount_log` و`channel` و`mcc` و`hour_of_day` و`is_night`. رقم العميل لا يدخل.
- المخرج: احتمال احتيال من 0 إلى 1، ثم قرار: `block` من 0.85، و`review` من 0.70، وإلا `allow`.
- البيانات: 5,000 عملية اصطناعية، منها 876 احتيال (17.5%).
- **AUC = 0.857**: النموذج يفرّق بين الاحتيال والسليم أفضل بكثير من رمي عملة (0.5)، لكنه ليس مثاليًا (1.0).
- عند حد الحظر 0.85: يمسك **10 من 876** فقط (1%) وبلا أي إنذار كاذب.
  عند 0.70: يمسك 91 (10%) مقابل 17 إنذارًا كاذبًا. عند 0.50 (للمقارنة): 286 (33%) مقابل 139.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- الدقة (accuracy) مضللة هنا: نموذج يقول `allow` لكل شيء "دقيق" بنسبة 82.5% ولا يمسك أي احتيال.
  لذلك نقرأ: كم أمسك، كم فاته، كم إنذار كاذب.
- الحدود صارمة جدًا: أغلب الاحتيال تحت 0.85. هذا قرار عمل (أقل إزعاج للعملاء الصادقين) وليس خطأ في الكود.
- الأرقام مقاسة على نفس البيانات التي تدرّب عليها النموذج، فهي متفائلة.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
النموذج مثل موظف يشوف كل عملية ويعطيها درجة شك من 0 إلى 1. ما يعرف تاريخ العميل، يعرف فقط المبلغ والقناة
ونوع المتجر والساعة. الإدارة قررت ما توقف إلا العمليات اللي شكها 0.85 أو أكثر، فيوقف قليل جدًا ويفوته كثير.
والدقة وحدها تكذب لما الاحتيال نادر، فلازم نشوف كم مسك وكم فاته.

**Open questions · أسئلة ما زالت مفتوحة**
هل خفض حد المراجعة أفضل للبنك؟ يعتمد على تكلفة الإنذار الكاذب مقابل تكلفة الاحتيال الفائت.

---

## Stage 1: Clean architecture · المعمارية النظيفة

**What we asked the agent · ما طلبناه من الوكيل**
افهمني ليش الكود القديم (`legacy/notebook_v1.py`) يطلع 182 نتيجة غلط بدون أي error، ثم أعد بناءه طبقات.

**What it built · ما بناه**
- `domain/entities.py`: أنواع البيانات و`to_features()`، المكان الوحيد لحساب الـ features.
- `domain/policies.py`: دالة `decide()`، قاعدة القرار (0.85 و0.70).
- `service/interfaces.py`: عقد `Model` (أي شيء عنده `predict_proba`).
- `service/scorer.py`: `FraudScorer`: features ثم تنبؤ ثم قرار، بدون أي مكتبة ML.
- `adapters/sklearn_model.py`: الملف الوحيد اللي يستورد scikit-learn وjoblib.
- `batch.py`: يربط القطع ويقيّم ملف CSV.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- الكود القديم: `4,818/5,000 rows match`. كل الصفوف الغلط وقتها الساعة 06 UTC.
- السبب: التدريب يستخدم `hour < 6` والتنبؤ يستخدم `hour <= 6` (training/serving skew).
- بعد إعادة البناء: `python -m fraud_service.batch` ثم `check_golden.py`: **5,000/5,000** ✅
- بنينا طبقات الـ domain والـ service بأيدينا في فرع تدريب (`lab1-practice`) لنفهمها.
- `grep` على استيرادات الـ service: لا sklearn ولا pandas ولا joblib.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
الكود القديم كان فيه `except Exception: p = 0.0`: لو انهار النموذج تصير الدرجة 0 والقرار `allow`،
يعني الاحتيال يمر بصمت. هذا أخطر من الخطأ الأصلي.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
قسّمنا الكود مثل البصلة: في الوسط قواعد العمل، وحولها الخدمة، وبعدها الأدوات مثل sklearn، وبرّا الـ API.
القاعدة: الاستيراد يتجه للداخل فقط. فلو غيّرنا النموذج نعدّل ملف واحد. والـ features صارت في مكان واحد،
فما يتكرر خطأ `<` و`<=`.

**Open questions · أسئلة ما زالت مفتوحة**
—

---

## Stage 2: FastAPI endpoint · نقطة نهاية FastAPI

**What we asked the agent · ما طلبناه من الوكيل**
ضع الـ scorer خلف API بعقد صارم: وش ترسل، وش يرجع، وخطأ واضح وآمن لأي شيء غلط.

**What it built · ما بناه**
- `api/schemas.py`: `PredictRequest` مع `extra="forbid"` وحدود لكل حقل.
- `api/app.py`: تحميل النموذج مرة وحدة عند التشغيل، warm-up، middleware للـ trace id، ومعالجات أخطاء بغلاف واحد.
- `api/routes.py`: `POST /v1/predict` و`GET /v1/health` و`GET /v1/ready`.
- `config.py`: إعدادات بأنواع محددة.
(Labs 2a and 2b came from the workshop's reference starting point, `lab3-start`; we studied them afterwards.)

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- طلب صحيح: `fraud_probability 0.62614, decision allow`.
- طلب بمبلغ سالب: `422 INVALID_REQUEST` بدون إعادة القيمة المرفوضة.
- الـ 40 طلب الخربان في `payloads/malformed/` كلها انرفضت (ثم 44 بعد الإضافة).
- اختبار الحمل: 486 req/s وp99 = 96ms داخل الحاوية.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
route التنبؤ `def` عادية وليس `async def`: الـ inference يوقف المعالج، وداخل `async` كان بيجمّد كل الطلبات
(المحاضرة قاست 5 req/s بدل 112).

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
الـ API باب له قوانين. pydantic حارس الباب: أي طلب ناقص أو غلط يرجع 422 قبل ما يوصل للنموذج.
وكل الأخطاء بنفس الشكل ومعها trace id، فالعميل يعرف وش صار والفريق يلقى الطلب في الـ logs.
و`/health` يقول "أنا حي" بينما `/ready` يقول "أقدر أخدم الحين".

**Open questions · أسئلة ما زالت مفتوحة**
—

---

## Stage 3: Container · الحاوية

**What we asked the agent · ما طلبناه من الوكيل**
وريني مشاكل الـ Dockerfile الساذج بعيني، ثم ابنِ الصحيح.

**What it built · ما بناه**
`Dockerfile` بمرحلتين، `.dockerignore`، `requirements.lock`، `docker-compose.yml` مع Redis، `configs/dev.env`.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- الصورة الساذجة: 3.12GB على القرص، و`cat leaked.env` طبع السر المزروع، و`whoami` = `root`.
- الصورة الصحيحة: 180MB مضغوطة (632MB مفكوكة، بـ `du -sh /` داخل الحاوية)، `whoami` = `appuser`، ولا يوجد `leaked.env`.
- تعديل سطر في الكود ثم إعادة البناء: **2 ثانية** بدل 2:54 دقيقة، لأن كل الطبقات `CACHED` ما عدا `COPY src/`.
- `docker compose ps`: الحاويتان `healthy`. الذاكرة 306MiB من 512MiB. الإيقاف 1.1 ثانية.
- جربنا المشروع من `git clone` جديد: اشتغل وصار `healthy`.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
أول بناء فشل: `typing-extensions==4.16.0` ما انلقى. ولّدنا `requirements.lock` من جديد بـ `uv` فاشتغل.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
الحاوية صندوق فيه الخدمة وكل ما تحتاجه، فتشتغل بنفس الطريقة في أي جهاز. نرتب الطبقات من الأقل تغيرًا للأكثر،
فتعديل الكود ما يعيد تثبيت المكتبات. ونبني بغرفتين: وحدة للتثبيت ووحدة نظيفة للتشغيل بدون root وبدون أسرار.

**Open questions · أسئلة ما زالت مفتوحة**
الحجم المفكوك 632MB فوق 600MB بقليل؛ حذف مجلدات `tests` من المكتبات ينزله تقريبًا لـ 500MB.

---

## Stage 4: Tests · الاختبارات

**What we asked the agent · ما طلبناه من الوكيل**
ابنِ هرم اختبارات بثلاث مستويات، ثم أرجع الخطأ القديم عمدًا وأشوف من يمسكه.

**What it built · ما بناه**
`tests/conftest.py` (نموذج وهمي `ConstantModel` وحقنه بـ `dependency_overrides`)، اختبارات unit وintegration
وbehavioural، ثم `tests/data/` (فحوصات البيانات) في المرحلة 6.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- Unit 16 في 0.01s، Integration 46، Behaviour 5 + golden في 9s. التغطية 100% (98% بعد الإضافة).
- غيّرت `hour < 6` إلى `hour <= 6` عمدًا: فشل `test_night_flag_boundaries[6-0]` (unit) في 0.67s،
  وفشل `test_golden_scores` على **182 صف** (نفس رقم المرحلة 1). ثم أرجعته و`git diff` صار فاضي.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
التغطية 100% لا تعني لا أخطاء: تقيس هل السطر اشتغل، لا هل الاختبار تأكد من النتيجة.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
اختبارات كثيرة صغيرة سريعة بنموذج وهمي، وأقل منها تختبر الـ API من برّا، وقليل يختبر النموذج الحقيقي:
هل الدرجة ثابتة لو غيّرنا رقم العميل؟ هل المبلغ الأكبر ما يبان أأمن؟ هل الـ 5,000 إجابة ما تغيرت؟
اختبار الـ unit يقول **ليش** صار الخطأ، والـ golden يقول **كم** أثّر.

**Open questions · أسئلة ما زالت مفتوحة**
—

---

## Stage 5: GitHub Actions · خط الأتمتة

**What we asked the agent · ما طلبناه من الوكيل**
pipeline يفحص كل تغيير ويبني الصورة ويختبرها وينشرها، وحماية للفرع، ثم PR سيئ عمدًا.

**What it built · ما بناه**
`.github/workflows/ci.yml` (lint وtest بالتوازي، ثم image-smoke، ثم publish على main فقط)،
`nightly.yml` (كل الاختبارات مع الـ golden كل ليلة)، وحماية `main` في إعدادات GitHub.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- أول تشغيل أخضر، والصورة انشرت: `docker pull ghcr.io/4onn/fraud-service:main` نزلت بدون تسجيل دخول.
- PR #1 فيه خطأين عمدًا (الـ service يستورد من الـ api، و`hour <= 6`): `lint` فشل عند Ruff (I001)،
  و`test` فشل عند `test_night_flag_boundaries[6-0]`، و`image-smoke` و`publish` ما اشتغلوا. الدمج ممنوع.
- أصلحناه بدون لمس أي اختبار، صار أخضر، ودمجناه.
- `image-smoke` نزل من 116s إلى 30s في التشغيل الثاني بسبب cache طبقات Docker.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
- الـ Actions كانت متوقفة لأن المستودع fork، فعّلناها يدويًا.
- خيار "Require approvals" منع الدمج لأنه ما كان فيه مراجع ثاني على المستودع وقتها، فشلناه.
- `# noqa: F401` أخفى الاستيراد عن قاعدة وحدة، لكن قاعدة ترتيب الاستيرادات مسكته.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
كل ما أرفع كود، GitHub يفحصه تلقائيًا: الأسلوب، الأنواع، المعمارية، الاختبارات، ثم يشغّل الصورة ويرسل لها
طلب. ولو شيء فشل، الحماية تمنع دخوله لـ main. فحتى لو نسيت أختبر، الآلة ما تنسى.

**Open questions · أسئلة ما زالت مفتوحة**
—

---

## Stage 6: Secrets · الأسرار

**What we asked the agent · ما طلبناه من الوكيل**
إعدادات تفشل مبكرًا، logs منظمة بدون أسرار، تمرين تسريب سر، ثم فحص أسرار تلقائي.

**What it built · ما بناه**
- `config.py`: `model_path` إجباري ويُتحقق منه، `extra="forbid"`، `registry_token` من نوع `SecretStr`.
- `logging_setup.py`: logs بصيغة JSON بتوقيت UTC، ودالة تخفي أي مفتاح حساس (`***MASKED***`).
- `configs/settings.example.env` (يوثّق الإعدادات بدون قيم)، و`.env` في `.gitignore` و`.dockerignore`.
- `INCIDENT.md`: خطة الاستجابة لتسريب سر.
- **فحص أسرار:** وظيفة `secrets-scan` (gitleaks، مثبّت بـ commit SHA) في الـ pipeline،
  و`.pre-commit-config.yaml` يشغّل gitleaks قبل كل commit محلي، و`.gitleaks.toml` باستثناء واحد مُراجَع.
- فحوصات البيانات `tests/data/test_data_checks.py` (9 اختبارات).

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
- `FRAUD_MODEL_PATH=/nope`: الخدمة رفضت تشتغل برسالة `model artefact not found: /nope`.
- من `service.log` فقط: median latency = 55.7ms، وكل أحداث الطلب `my-trace-1` (حدثين بنفس الـ trace id).
- سجّلنا `token="abc123"` عمدًا: ظهر `"token": "***MASKED***"`.
- التمرين: commit فيه token وهمي ثم commit يحذفه، و`git log -p -S` لسه يلقاه في التاريخ. حذفنا الـ commits
  قبل أي push. الدرس: **غيّر السر أولًا**، ثم نظّف التاريخ، ثم أضف فاحص.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
حذف السطر ما يحذف السر: git يحفظ كل نسخة من كل ملف.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
السر ما يدخل git ولا الصورة ولا الـ logs. الإعدادات تجي من متغيرات البيئة وتنفحص عند التشغيل. ولو تسرّب سر،
أول شيء تغيّره، لأن حذفه من الكود ما يرجّع النسخ اللي أحد أخذها. والـ pipeline والـ pre-commit يفحصون
كل تغيير قبل ما يدخل. وفي GitHub نفسه: الـ `GITHUB_TOKEN` قصير العمر، وصلاحية النشر للوظيفة اللي تنشر بس.

**Open questions · أسئلة ما زالت مفتوحة**
الخطوة التالية للأسرار: SOPS مع age لأسرار مشفرة داخل المستودع، وOIDC بدل مفاتيح سحابية مخزنة لو نشرنا على سحابة.

---

## Extension: stricter firewall · الإضافة: جدار حماية أشد

**What we asked the agent · ما طلبناه من الوكيل**
ارفض المبالغ اللي تجي كنص أو `true/false`، والأوقات بدون منطقة زمنية.

**What it built · ما بناه**
`strict=True` على `amount_sar`، و`AwareDatetime` على `timestamp`، و4 payloads جديدة، و`tests/unit/test_schemas.py`،
وتحويل الوقت لـ UTC داخل `to_features()`.

**What we checked, and what we saw · ما تحققنا منه وما رأيناه**
كل الفحوصات خضراء، والـ golden 5,000/5,000 ما تغيّر.

**What surprised us or went wrong · ما فاجأنا أو ما تعثرنا فيه**
اكتشفنا خطأ skew ثاني: عميل يرسل `06:30+03:00` (الرياض) كانت ساعته تنحسب 6 بدل 3 UTC، فيتغير `is_night`.

**How we would explain this stage to a colleague · كيف نشرح هذه المرحلة لزميل**
pydantic افتراضيًا "يخمّن": يحوّل "250" لرقم ويقبل وقت بدون منطقة. في خدمة احتيال التخمين خطر، فصار يرفض.
وتشديد حقل يكسر العقد مع العملاء، فلو الخدمة في الإنتاج كنا بنطلقه في `/v2`.

**Open questions · أسئلة ما زالت مفتوحة**
—
