// Example questions are user data, not interface text: they stay in the language the clerk would
// type them in, so they are not translated.
export const EXAMPLE_QUESTIONS: readonly string[] = [
  "My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?",
  "मेरा प्लॉट 200 वर्ग मीटर का है और सड़क 9 मीटर चौड़ी है। आगे कितनी जगह छोड़नी होगी?",
  "How do I pay property tax online?",
];

/** Shorter text for the chip: the full question is sent when it is chosen. */
export const EXAMPLE_LABELS: readonly string[] = [
  "200 sq m plot, 9 m road: front gap, floors, fee?",
  "मेरा 200 वर्ग मीटर का प्लॉट…",
  "How to pay property tax?",
];
