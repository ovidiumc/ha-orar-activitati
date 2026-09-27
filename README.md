# Orar & Activități pentru Home Assistant

Integrare custom care ține **orarul săptămânal al fiecărui copil** — orele de școală, pauzele și activitățile de după masă — și îți arată, în orice moment, **ce e acum**, **ce urmează azi** și **ce e mâine**.

Vine la pachet cu un **card Lovelace** care se înregistrează singur, deci nu trebuie să adaugi nimic manual în Resources.

Nu comunică cu niciun server: totul e calculat local din datele introduse de tine (`iot_class: calculated`).

---

## Ce obții

Pentru fiecare copil adăugat se creează un **device** cu patru senzori:

| Senzor | Stare | Exemplu entity_id |
|---|---|---|
| Acum | denumirea activității care se desfășoară acum, sau `unknown` | `sensor.tudor_acum` |
| Urmează | denumirea următoarei activități (se uită și în zilele următoare) | `sensor.tudor_urmeaza` |
| Azi | numărul de intrări din ziua curentă | `sensor.tudor_azi` |
| Mâine | numărul de intrări din **următoarea zi cu program** | `sensor.tudor_maine` |

Senzorii se recalculează **exact la fiecare început și sfârșit de oră** și la miezul nopții — deci `Acum` se schimbă în clipa în care se termină ora, nu la următorul minut rotund.

### Zilele libere

Într-o **zi liberă** orele de școală și pauzele dispar din orar, dar **activitățile rămân** — o sărbătoare închide școala, nu anulează antrenamentul de fotbal.

Zilele libere vin din două surse:

**Sărbătorile legale românești** se calculează singure, inclusiv Paștele și Rusaliile, care se mișcă de la an la an. Folosesc biblioteca `holidays`, aceeași pe care o folosește și senzorul Workday din Home Assistant. Le poți opri din *Configurează → Zile libere → Sărbători legale automate*.

**Vacanțele școlare** le introduci tu. Cel mai rapid e **Configurează → Zile libere → Importă un an școlar întreg**, unde lipești tot anul dintr-o dată, o perioadă pe linie:

```
Vacanța de toamnă | 24.10.2026 | 01.11.2026
Vacanța de iarnă | 23.12.2026 | 10.01.2027
```

Datele se acceptă atât `23.12.2026` cât și `2026-12-23`. Liniile goale și cele care încep cu `#` sunt ignorate. **Dacă măcar o linie e greșită, nu se importă nimic** — altfel o greșeală de tastare ar strecura o zi greșită în calendar în timp ce restul par în regulă.

Una câte una se adaugă din: *Configurează → Zile libere → Adaugă o perioadă liberă*. O perioadă acoperă o vacanță întreagă (prima zi → ultima zi); pentru o singură zi liberă pui aceeași dată de două ori. Perioadele sunt per copil, pentru că frații pot fi la școli cu vacanțe diferite.

Dacă o perioadă introdusă de tine acoperă o sărbătoare legală, **denumirea ta câștigă** — 25 decembrie din interiorul vacanței de iarnă se afișează ca „Vacanța de iarnă", nu ca „Crăciunul".

Senzorii expun `zi_libera` și `denumire_zi_libera` pentru ziua pe care o descriu, iar cardul afișează o bandă cu motivul.

### Weekendul

Senzorul **Mâine** nu arată pur și simplu ziua următoare, ci **următoarea zi care are ceva în ea**, căutând până la o săptămână înainte. Școala e de luni până vineri, așa că vineri seara „mâine" ar fi o sâmbătă goală, iar duminică ai vedea gol în loc de orarul de luni.

Activitățile de weekend **nu** sunt sărite: regula e „următoarea zi cu program", deci un antrenament sâmbătă are prioritate față de luni.

| Când ești | Ce arată banda |
|---|---|
| Luni–joi | ziua de mâine |
| Vineri, fără activități în weekend | **Luni** |
| Vineri, cu activitate sâmbătă | **Sâmbătă** |
| Sâmbătă / duminică, fără activități | **Luni** |

Atributul `este_maine` spune dacă ziua chiar e mâine. Cardul îl folosește ca să scrie „MÂINE (LUNI, 28 SEPT)" doar când e adevărat, altfel doar numele zilei. Dacă cei doi copii au zile următoare diferite, banda trece pe titlul „Urmează" și fiecare rând își poartă ziua.

### Atribute

Toți cei patru senzori poartă identitatea copilului, ca să poți construi un card întreg dintr-o singură entitate:

| Atribut | Exemplu | Descriere |
|---|---|---|
| `vizualizare` | `acum` | Care dintre cei patru senzori e — cardul se orientează după el |
| `copil` | `Tudor` | Numele copilului |
| `clasa` | `Cls. IV` | Clasa, dacă ai completat-o |
| `culoare` | `#2196f3` | Culoarea de accent a copilului |

**Acum** și **Urmează** adaugă detaliile intrării:

| Atribut | Exemplu |
|---|---|
| `liber` | `false` — `true` când nu e nimic în desfășurare |
| `interval` | `11:30 - 13:00` |
| `ora_inceput` / `ora_sfarsit` | `11:30` / `13:00` |
| `titlu` | `Matematică` |
| `sala` | `Sala 104` |
| `tip` | `scoala`, `activitate` sau `pauza` |
| `online` | `false` |
| `locatie_url` | link de hartă sau de întâlnire |
| `iconita` | `mdi:school` |
| `minute_ramase` | doar pe **Acum** — câte minute mai sunt până se termină |
| `incepe_in`, `data`, `zi` | doar pe **Urmează** — peste câte minute începe și în ce zi |

**Azi** și **Mâine** adaugă ziua întreagă:

| Atribut | Descriere |
|---|---|
| `data` | data în ISO (`2026-09-24`) |
| `zi` | numele zilei în română (`Joi`) |
| `este_maine` | `true` doar dacă ziua e chiar cea de mâine |
| `zi_libera` | `true` dacă școala e închisă în ziua aceea |
| `denumire_zi_libera` | de ce — `Vacanța de iarnă`, `Ziua Națională a României` |
| `activitati` | lista completă a intrărilor zilei, în ordine cronologică |
| `activitati_dupa_masa` | doar intrările de tip **activitate** |

> `activitati_dupa_masa` filtrează după *tipul* intrării, nu după oră. Așa, un curs de desen online la 13:45 și un antrenament la 16:30 sunt amândouă activități, în timp ce o oră de școală la 17:00 nu e.

---

## Instalare

### Prin HACS (recomandat)

1. HACS → meniul cu trei puncte → **Custom repositories**
2. Adaugă `https://github.com/ovidiumc/ha-orar-activitati`, categoria **Integration**
3. Caută **Orar & Activitati** în HACS și apasă **Download**
4. Repornește Home Assistant

### Manual

1. Copiază folderul `custom_components/ha_orar_activitati/` în directorul `config/custom_components/` al instanței tale
2. Repornește Home Assistant

Structura finală trebuie să arate așa:

```
config/
└── custom_components/
    └── ha_orar_activitati/
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── schedule.py
        ├── sensor.py
        ├── strings.json
        ├── freedays.py
        ├── brand/
        │   ├── icon.png
        │   └── icon@2x.png
        ├── frontend/
        │   └── orar-activitati-card.js
        └── translations/
            ├── en.json
            └── ro.json
```

---

## Configurare

### 1. Adaugă copiii

**Settings → Devices & Services → Add Integration → Orar & Activitati**

| Câmp | Obligatoriu | Observații |
|---|---|---|
| Numele copilului | da | Devine ID-ul unic |
| Clasa | nu | Apare lângă nume pe card, ex. `Cls. IV` |
| Culoare | nu | Orice culoare CSS, ex. `#ff9800`. Colorează coloana copilului |

Repetă pentru fiecare copil.

### 2. Construiește orarul

**Configurează** pe device-ul copilului → se deschide un meniu:

- **Adaugă o intrare** — o intrare nouă în orar
- **Modifică o intrare** / **Șterge intrări**
- **Zile libere (vacanțe)** — sărbători legale automate + vacanțele tale
- **Datele copilului** — nume, clasă, culoare
- **Gata (salvează)** — scrie modificările și reîncarcă senzorii

O intrare are:

| Câmp | Obligatoriu | Observații |
|---|---|---|
| Denumire | da | `Matematică`, `Antrenament Fotbal` |
| Zilele săptămânii | da | **Mai multe deodată** — o materie ținută luni și miercuri e o singură intrare |
| Ora de început / sfârșit | da | Sfârșitul trebuie să fie după început |
| Tip | da | `Școală`, `Activitate` sau `Pauză / masă` |
| Sala / locația | nu | `Sala 104` |
| Online | nu | Pune o iconiță de laptop pe card |
| Link locație | nu | Link de hartă sau de întâlnire, afișat ca iconiță |

> Modificările din meniu se salvează **doar** când alegi **Gata**. Dacă închizi dialogul pe la mijloc, orarul rămâne cum era.

### 3. Pune cardul pe dashboard

Cardul se încarcă automat împreună cu integrarea. Adaugă-l cu **Add card → Custom: Orar & Activități**, sau în YAML:

```yaml
type: custom:orar-activitati-card
```

Atât — găsește singur toți copiii configurați. Dacă vrei să controlezi ordinea sau să afișezi doar o parte:

```yaml
type: custom:orar-activitati-card
title: Organizare activități și școală
copii:
  - Tudor
  - Bogdan
maine_maxim: 2
arata_maine: true
```

| Opțiune | Implicit | Descriere |
|---|---|---|
| `title` | `Organizare activități și școală` | Titlul cardului |
| `copii` | toți, alfabetic | Numele copiilor, în ordinea coloanelor |
| `maine_maxim` | `2` | Câte intrări de mâine listează banda de jos, per copil |
| `arata_maine` | `true` | Ascunde banda de jos cu `false` |

Pe ecran îngust coloanele se așază una sub alta.

---

## Exemple de automatizări

Notificare cu 15 minute înainte de o activitate de după masă:

```yaml
automation:
  - alias: Reamintire activitate
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tudor_urmeaza
        attribute: incepe_in
        below: 16
    conditions:
      - condition: state
        entity_id: sensor.tudor_urmeaza
        attribute: tip
        state: activitate
    actions:
      - action: notify.pixel_7_pro
        data:
          title: "Tudor — în 15 minute"
          message: >-
            {{ state_attr('sensor.tudor_urmeaza', 'titlu') }}
            ({{ state_attr('sensor.tudor_urmeaza', 'interval') }})
```

Rezumatul serii pentru ziua următoare:

```yaml
{% for slot in state_attr('sensor.tudor_maine', 'activitati') %}
{{ slot.interval }} — {{ slot.titlu }}{% if slot.sala %} ({{ slot.sala }}){% endif %}
{% endfor %}
```

Câte activități de după masă are Bogdan azi:

```yaml
{{ state_attr('sensor.bogdan_azi', 'activitati_dupa_masa') | count }}
```

---

## Iconița

Integrarea își poartă propria iconiță, în `custom_components/ha_orar_activitati/brand/`. Home Assistant o preia automat de acolo, fără nicio configurare — începând cu **HA 2026.3**. Pe versiuni mai vechi, locul integrării în listă rămâne cu placeholderul „icon not available"; singura cale acolo e un PR în [home-assistant/brands](https://github.com/home-assistant/brands), sub `custom_integrations/ha_orar_activitati/`.

---

## Licență

AGPL-3.0 — vezi [LICENSE](LICENSE).
