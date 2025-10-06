import functions from 'firebase-functions';
import admin from 'firebase-admin';
import fetch from 'node-fetch';

admin.initializeApp();
const db = admin.firestore();

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent';

async function callGemini(answer, existingCategories) {
  const currentCategoriesList = existingCategories.join(', ');
  const system_prompt = `You are an AI Categorization Engine for academic interests.\n\nCurrent existing categories are: ${currentCategoriesList || 'None'}.\n\nRULES:\n1. If the user's answer strongly aligns with an EXISTING category, use that category name exactly.\n2. If the user's answer is unique and represents a NEW, distinct topic, create a CONCISE (2-4 word) and descriptive new category name.\n3. Return JSON: {"category_name": string, "is_new": boolean}`;

  const payload = {
    contents: [{ parts: [{ text: `User's interest: '${answer}'. Classify this interest.` }] }],
    systemInstruction: { parts: [{ text: system_prompt }] },
    generationConfig: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: 'OBJECT',
        properties: {
          category_name: { type: 'STRING' },
          is_new: { type: 'BOOLEAN' }
        },
        required: ['category_name', 'is_new']
      }
    }
  };

  const res = await fetch(`${API_URL}?key=${GEMINI_API_KEY}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Gemini error: ${res.status}`);
  const json = await res.json();
  const text = json?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Malformed Gemini response');
  return JSON.parse(text);
}

function docIdFromQuestion(question) {
  return question.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120) || 'general';
}

export const api = functions.https.onRequest(async (req, res) => {
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(204).send('');

  try {
    const url = new URL(req.url, `https://${req.hostname}`);
    const pathname = url.pathname.replace(/^\/api/, '') || '/';
    const p = url.searchParams.get('p') || 'default';

    if (pathname === '/questions' && req.method === 'GET') {
      const doc = await db.collection('presentations').doc(p).get();
      const data = doc.exists ? doc.data() : {};
      const questions = Array.isArray(data?.questions) ? data.questions : [];
      return res.json(questions);
    }

    if (pathname === '/categories' && req.method === 'GET') {
      const q = url.searchParams.get('question') || 'General';
      const qId = docIdFromQuestion(q);
      const docRef = db.collection('presentations').doc(p).collection('categories_by_question').doc(qId);
      const snap = await docRef.get();
      return res.json(snap.exists ? (snap.data() || {}) : {});
    }

    if (pathname === '/categorize' && req.method === 'POST') {
      const { answer, question } = req.body || {};
      if (!answer || typeof answer !== 'string' || !answer.trim()) {
        return res.status(400).json({ detail: 'Answer cannot be empty.' });
      }
      const qText = (question || 'General').trim() || 'General';
      const qId = docIdFromQuestion(qText);

      // Get existing categories
      const catRef = db.collection('presentations').doc(p).collection('categories_by_question').doc(qId);
      const catSnap = await catRef.get();
      const categories = catSnap.exists ? (catSnap.data() || {}) : {};
      const existingCategoryNames = Object.keys(categories);

      const categorization = await callGemini(answer.trim(), existingCategoryNames);
      const category = (categorization.category_name || '').trim();
      let is_new = !!categorization.is_new;
      if (!category) return res.status(500).json({ detail: 'AI did not return a category.' });

      const arr = Array.isArray(categories[category]) ? categories[category] : [];
      arr.push(answer.trim());
      categories[category] = arr;

      await catRef.set(categories, { merge: true });
      // ensure presentation doc exists and register question
      await db.collection('presentations').doc(p).set({
        questions: admin.firestore.FieldValue.arrayUnion(qText)
      }, { merge: true });

      return res.json({
        message: `Answer successfully categorized under: '${category}'`,
        category,
        is_new,
        all_categories: categories
      });
    }

    if (pathname === '/admin/add_question' && req.method === 'POST') {
      const question = (req.body?.question || '').trim();
      if (!question) return res.status(400).json({ detail: 'Question is required.' });
      await db.collection('presentations').doc(p).set({
        questions: admin.firestore.FieldValue.arrayUnion(question)
      }, { merge: true });
      return res.json({ ok: true });
    }

    if (pathname === '/admin/download_csv' && req.method === 'GET') {
      const catsCol = db.collection('presentations').doc(p).collection('categories_by_question');
      const snaps = await catsCol.listDocuments();
      let csv = 'Question,Category,Answer\n';
      for (const docRef of snaps) {
        const snap = await docRef.get();
        const qId = docRef.id;
        const data = snap.exists ? snap.data() : {};
        const questionText = qId.replace(/-/g, ' '); // best-effort
        for (const [category, answers] of Object.entries(data)) {
          for (const ans of (answers || [])) {
            csv += `"${questionText}","${category}","${String(ans).replace(/"/g, '""')}"\n`;
          }
        }
      }
      res.set('Content-Disposition', 'attachment; filename="data.csv"');
      res.set('Content-Type', 'text/csv');
      return res.send(csv);
    }

    return res.status(404).json({ detail: 'Not found' });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ detail: 'Server error' });
  }
});


