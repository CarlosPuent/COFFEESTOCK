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

  /* --- Registros por página: recarga la tabla desde la primera página --- */
  function iniciarTamanoPagina() {
    document.querySelectorAll("select[data-por-pagina]").forEach(function (select) {
      select.addEventListener("change", function () {
        var base = select.dataset.base;
        window.location.search = (base ? base + "&" : "") + "por_pagina=" + select.value;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    iniciarFechas(document);
    iniciarTamanoPagina();
  });

  window.CoffeeStock = { iniciarFechas: iniciarFechas };
})();
