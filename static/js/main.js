// Warn (client-side) if someone picks more than 5 photos on the sell form.
document.addEventListener("DOMContentLoaded", () => {
  const photoInput = document.getElementById("photos");
  if (!photoInput) return;

  const hint = photoInput.parentElement.querySelector(".field-hint");
  const baseHint = hint ? hint.textContent : "";

  photoInput.addEventListener("change", () => {
    const count = photoInput.files.length;
    if (!hint) return;
    if (count > 5) {
      hint.textContent = `Only the first 5 photos will be kept (you selected ${count}).`;
      hint.style.color = "var(--orange)";
    } else {
      hint.textContent = baseHint;
      hint.style.color = "";
    }
  });
});
