/* CoffeeStock — comportamiento común a todas las pantallas. */
(function () {
  "use strict";

  /* --- Selectores de fecha en español (dd/mm/aaaa) ---
     El campo real sigue enviando AAAA-MM-DD al servidor; el usuario ve y
     escribe la fecha en formato local. */
  function iniciarFechas(contexto) {
    if (typeof flatpickr === "undefined") return;
    (contexto || document).querySelectorAll("input[data-fecha]").forEach(function (input) {
      if (input._flatpickr) return;
      flatpickr(input, {
        locale: "es",
        dateFormat: "Y-m-d",
        altInput: true,
        altFormat: "d/m/Y",
        allowInput: true,
        disableMobile: true,
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    iniciarFechas(document);
  });

  window.CoffeeStock = { iniciarFechas: iniciarFechas };
})();
