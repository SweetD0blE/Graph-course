const registerForm = document.getElementById("registerForm");
const password = document.getElementById("password");
const passwordRepeat = document.getElementById("passwordRepeat");
const formMessage = document.getElementById("formMessage");

function validatePasswords() {
  if (!password || !passwordRepeat || !formMessage) {
    return true;
  }

  const hasValues = password.value.length > 0 && passwordRepeat.value.length > 0;

  if (!hasValues) {
    formMessage.textContent = "";
    formMessage.classList.remove("is-success");
    return true;
  }

  if (password.value !== passwordRepeat.value) {
    formMessage.textContent = "Пароли не совпадают";
    formMessage.classList.remove("is-success");
    return false;
  }

  formMessage.textContent = "Пароли совпадают";
  formMessage.classList.add("is-success");
  return true;
}

password?.addEventListener("input", validatePasswords);
passwordRepeat?.addEventListener("input", validatePasswords);

registerForm?.addEventListener("submit", (event) => {
  if (!validatePasswords()) {
    event.preventDefault();
    passwordRepeat?.focus();
  }
});
