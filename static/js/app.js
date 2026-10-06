document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash-close").forEach(button => {
    button.addEventListener("click", () => button.closest(".flash").remove());
  });
  document.querySelectorAll("form[data-confirm]").forEach(form => {
    form.addEventListener("submit", event => {
      if (!window.confirm(form.dataset.confirm || "Are you sure?")) event.preventDefault();
    });
  });
  const issue = document.querySelector("#issue_date");
  const expiry = document.querySelector("#expiry_date");
  if (issue && expiry) {
    issue.addEventListener("change", () => { expiry.min = issue.value; });
    expiry.addEventListener("change", () => {
      if (issue.value && expiry.value && expiry.value < issue.value) {
        expiry.setCustomValidity("Expiry date cannot be earlier than issue date.");
      } else {
        expiry.setCustomValidity("");
      }
    });
  }
});
