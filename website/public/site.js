// اطلاعات انتشار از همان میزبان خوانده می‌شود؛ نشانی شخص ثالث وارد صفحه نمی‌شود.
async function showRelease() {
  const button = document.getElementById("installer-download");
  const status = document.getElementById("release-status");
  try {
    const response = await fetch("/release.json", { cache: "no-store" });
    if (!response.ok) throw new Error("release unavailable");
    const release = await response.json();
    document.getElementById("release-label").textContent = `نسخهٔ آزمایشی ${release.version}`;
    if (!release.available) {
      button.textContent = "فایل نصب در حال آماده‌سازی است";
      status.textContent = "انتشار دانلود هنوز کامل نشده است؛ راهنمای شروع را در ادامه بخوانید.";
      return;
    }
    button.href = release.downloadPath;
    button.removeAttribute("aria-disabled");
    button.textContent = "دریافت نصب‌کنندهٔ ویندوز ↓";
    status.textContent = `نسخهٔ ${release.version} · ${(release.size / 1024 ** 2).toFixed(1)} مگابایت · بدون امضای دیجیتال`;
    const checksum = document.getElementById("checksum-download");
    checksum.href = release.checksumPath;
    checksum.hidden = false;
    document.getElementById("hash-command").textContent = `Get-FileHash .\\${release.filename} -Algorithm SHA256`;
  } catch {
    button.textContent = "وضعیت دانلود در دسترس نیست";
    status.textContent = "اتصال اینترنت را بررسی و صفحه را دوباره باز کنید.";
  }
}

showRelease();
