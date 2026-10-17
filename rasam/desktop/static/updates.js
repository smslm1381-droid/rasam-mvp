async function refreshUpdates() {
  try {
    const data = await (await request('/updates')).json();
    if (!data.available) return;
    $('update-description').textContent = `نسخهٔ تازهٔ رصام (${data.version}) آماده است.`;
    $('update-download').href = data.download_url;
    $('update-banner').hidden = false;
  } catch (_) {
    // بررسی نسخه نباید کاربر را هنگام قطع اینترنت از پرسیدن سؤال بازدارد.
  }
}
refreshUpdates();
