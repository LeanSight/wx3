# Growing Object-Oriented Software, Guiado por Tests, Sin Mocks

Esta es una reseña del libro *Growing Object-Oriented Software, Guided by Tests* (GOOS, abreviado), en la que mostraré cómo implementar el proyecto de ejemplo del libro de una manera que no requiere mocks para ser testeado.

> **Nota de adaptación:** Los ejemplos de código originales están en Java (libro) y C# (implementación alternativa del autor). Esta versión los traduce a **Python idiomático moderno**, manteniendo fielmente la arquitectura y los conceptos.

---

## Por qué escribo esta reseña

Si sigues este blog con regularidad, probablemente hayas notado que estoy bastante en contra de usar mocks en los tests. Por eso, a veces recibo comentarios que señalan que el código que tomo como ejemplo simplemente no emplea el mocking correctamente, y que por tanto mis argumentos no son del todo válidos.

Así que aquí tomaré el ejemplo más canónico del uso de mocks que pude encontrar —el del libro GOOS— y mostraré cómo el uso de mocks daña el diseño. También mostraré cuánto más simple se vuelve el código cuando eliminas los mocks y aplicas las pautas que describí en los posts anteriores de esta serie.

La segunda razón de esta reseña es señalar qué consejos del libro considero buenos y cuáles no. Hay muchos tips y pautas excelentes en el libro, pero también hay consejos que pueden dañar tu aplicación si los implementas en la práctica.

---

## Las partes buenas

Empezaré con las partes buenas, la mayoría de las cuales se encuentran en las dos primeras secciones del libro.

Los autores hacen un gran énfasis en que los tests son una red de seguridad que ayuda a detectar errores de regresión. Este es, en efecto, un rol importante de los tests. De hecho, creo que es el más importante. Proporciona confianza que, a su vez, permite avanzar rápidamente hacia los objetivos de negocio. Es difícil sobreestimar cuánto más productivo te vuelves cuando tienes la certeza de que la feature o el refactoring que acabas de implementar no rompe la funcionalidad existente. Esa sensación es liberadora.

El libro también describe la importancia de configurar el entorno de despliegue en etapas tempranas. Esa debería ser tu primera prioridad al iniciar un proyecto desde cero, ya que te permite revelar posibles problemas de integración de inmediato, antes de escribir una cantidad sustancial de código.

Para lograrlo, los autores proponen construir un **Walking Skeleton**: la versión más simple posible de tu aplicación que al mismo tiempo atraviesa todas las capas de extremo a extremo. Por ejemplo, si es una aplicación web, el skeleton puede mostrar una página HTML simple que renderice algún string desde la base de datos real. Este skeleton debería estar cubierto con un test end-to-end que se convierta en el primer test de tu test suite.

Esta técnica te permite enfocarte en construir un pipeline de despliegue sin prestar demasiada atención a la arquitectura de la aplicación. Cuanto más rápido obtengas feedback, mejor.

El libro propone un ciclo TDD de dos niveles:

```
Escribir test end-to-end fallido
  -> ciclo interno: test unitario fallido -> hacer pasar -> refactorizar
  -> repetir hasta que el test end-to-end pase
```

Es decir, comenzar cada feature con un test end-to-end y abrirse camino hasta hacerlo pasar con el ciclo regular red-green-refactor.

Los tests end-to-end aquí actúan más como una medición del progreso, y algunos de ellos pueden fallar porque las features que cubren aún están en desarrollo. Los unit tests, en cambio, son una suite de regresión y deben pasar en todo momento.

Es importante que los tests end-to-end toquen la mayor cantidad posible de sistemas externos. Eso te ayudará a revelar problemas de integración. Al mismo tiempo, los autores admiten que a menudo tendrás que simular algunos sistemas externos de todas formas. Es una pregunta abierta qué incluir en los tests end-to-end; debes tomar una decisión en cada caso por separado. Por ejemplo, si trabajas con un sistema bancario externo, no es práctico crear transacciones de dinero reales cada vez que quieres testear la integración con él.

El libro propone extender el clásico ciclo TDD de 3 pasos con un paso adicional: mejorar el mensaje de diagnóstico.

```
Escribir test fallido
  -> hacer claro el mensaje de fallo
  -> hacer pasar el test
  -> refactorizar
```

Esta práctica ayuda a asegurarse de que cuando un test falle, podrás entender qué está mal con tu código solo mirando el mensaje de fallo, sin necesidad de lanzar el debugger.

Los autores aconsejan desarrollar la aplicación end-to-end desde el principio. No pases demasiado tiempo puliendo tu arquitectura; comienza con alguna entrada que venga del mundo exterior (por ejemplo, desde la UI) y procesa esa entrada de manera completa, hasta el nivel de base de datos, con la mínima cantidad de código posible. En otras palabras, trabaja con slices verticales de funcionalidad; no construyas la arquitectura por adelantado.

Otro gran consejo es el de hacer unit testing del comportamiento, no de los métodos. A menudo no son lo mismo, ya que una sola unidad de comportamiento puede cruzar múltiples métodos a la vez. Esta práctica te ayudará a construir tests que respondan la pregunta "qué" en lugar de "cómo".

Otro punto interesante es la context-independence del SUT:

> Cada objeto debería no tener conocimiento incorporado sobre el sistema en el que se ejecuta.

Esto es básicamente el concepto de aislamiento del domain model. Las clases de dominio no deberían conocer ni depender de ningún sistema externo. Deberías poder extraerlas del contexto en el que se ejecutan sin esfuerzo adicional. Además de la capacidad de testear fácilmente el código, esta técnica lo simplifica enormemente, ya que puedes enfocarte en tu domain model sin prestar atención a preocupaciones no relacionadas con tu dominio.

El libro propone la famosa regla **"Only mock types that you own"** (solo mockea tipos que tú posees). Es decir, deberías usar test doubles solo para sustituir los tipos que tú mismo creaste. De lo contrario, no tienes garantía de imitar su comportamiento correctamente. La pauta básicamente se reduce a escribir tus propios gateways para cada servicio externo que uses.

Es interesante que los autores rompan esta regla en un par de ocasiones a lo largo del libro. Los tipos externos en esos casos son bastante simples, así que no tiene mucho sentido sustituirlos por implementaciones propias.

Por cierto, Gojko Adzic en su charla *Test automation without a headache* refina esta regla a **"Only mock types that you understand"** (solo mockea tipos que comprendes). Y creo que esta versión se ajusta mejor a la intención detrás de la pauta. Si entiendes completamente cómo funciona un tipo, no importa quién sea su autor; puedes simular completamente su comportamiento con un mock y, por tanto, no necesitas wrappers adicionales encima de él.

---

## Las partes problemáticas

A pesar de todos los excelentes tips y técnicas que propone el libro, la cantidad de consejos potencialmente dañinos es bastante sustancial.

El libro es un fuerte defensor del estilo de unit testing por **verificación de colaboración**, incluso cuando se trata de comunicación entre objetos individuales dentro del domain model. En mi opinión, es el principal defecto del libro. Todos los demás defectos se derivan de este.

Para justificar este enfoque, los autores aluden a la definición de Object-Oriented Design dada por Alan Kay:

> La gran idea es la "mensajería" [...] La clave para hacer sistemas grandes y escalables es mucho más diseñar cómo se comunican sus módulos que cuáles deberían ser sus propiedades y comportamientos internos.

Luego concluyen que las interacciones entre objetos es en lo que deberías enfocarte principalmente en los unit tests. Por esta lógica, el patrón de comunicación entre clases es lo que esencialmente comprende el sistema e identifica su comportamiento.

Hay dos problemas con este punto de vista. Primero, no traería aquí la definición de OOD de Alan Kay. Es bastante vaga para construir un argumento tan fuerte sobre ella, y tiene poco que ver con cómo lucen los lenguajes OOP fuertemente tipados modernos hoy en día.

El segundo problema con esta línea de pensamiento es que las clases individuales son demasiado de grano fino para tratarlas como agentes de comunicación independientes. El patrón de comunicación entre ellas tiende a cambiar con frecuencia y tiene poca correlación con el resultado final que deberíamos apuntar a verificar.

Como mencioné en el post anterior, la forma en que las clases dentro del domain model se comunican entre sí es un detalle de implementación. El patrón de comunicación solo se convierte en parte de la API cuando cruza el límite del sistema: cuando tu domain model comienza a interactuar con servicios externos. Desafortunadamente, el libro no hace esta distinción.

Las desventajas del enfoque que propone el libro se vuelven evidentes cuando consideras el proyecto de ejemplo que recorre en la 3ª parte. No solo enfocarse en la colaboración entre clases conlleva unit tests frágiles que se acoplan a los detalles de implementación del SUT, sino que también conduce a un diseño excesivamente complicado con dependencias cíclicas, header interfaces y un número excesivo de capas de indirección.

En el resto de este artículo, te mostraré cómo se puede modificar la implementación del libro y qué efecto tiene esa modificación en el test suite.

---

## El proyecto de ejemplo

Antes de entrar en el código, déjame presentar primero el dominio del problema. La aplicación de ejemplo es **Auction Sniper**: un robot diseñado para participar en subastas online. Cada fila en la grilla representa un agente separado que escucha los eventos provenientes del servidor de subastas y responde a ellos en consecuencia. Las reglas de negocio pueden resumirse con la siguiente máquina de estados:

```
JOINING
  -- Close event --> LOST
  -- Price event (bid needed, within stop_price) --> BIDDING

BIDDING
  -- Price event (our bid leading) --> WINNING
  -- Price event (need to rebid, within stop_price) --> BIDDING
  -- Close event --> LOST

WINNING
  -- Price event (other bid leads) --> BIDDING
  -- Close event --> WON
```

Cada agente (también llamados Auction Snipers) comienza en el estado *Joining*. Luego espera a que el servidor envíe un evento sobre el estado actual de la subasta: cuál fue el último precio, de qué usuario, y cuál debería ser el incremento mínimo para superar el último precio. Este evento se llama **Price event**.

Si la oferta requerida es menor que el *stop price* que el usuario configuró para ese artículo, la aplicación envía una oferta y pasa al estado *Bidding*. Si un nuevo Price event muestra que nuestra oferta va ganando, el Sniper no hace nada y pasa al estado *Winning*. Finalmente, el segundo evento que puede enviar el servidor de subastas es el **Close event**. Cuando llega, la aplicación mira en qué estado se encuentra actualmente para el artículo dado. El estado *Winning* pasa a *Won*, y todos los demás pasan a *Lost*.

Básicamente, lo que tenemos aquí es un participante automático de subastas que envía comandos al servidor y mantiene una máquina de estados interna.

---

## Problemas del diseño original (GOOS)

La arquitectura propuesta en el libro tiene tres problemas principales:

**Header interfaces**: interfaces que imitan completamente a la única clase que las implementa (Auction/XMPPAuction, AuctionEventListener/AuctionSniper, etc.). Las interfaces con una única implementación no representan una abstracción y generalmente se consideran un code smell.

**Dependencias ciclicas**: por ejemplo, XMPPAuction notifica a AuctionSniper, que referencia a SnipersTableModel, que crea SniperLauncher, que regresa a AuctionSniper. Las dependencias cíclicas añaden tremenda carga cognitiva: para entender una clase necesitas cargar todo el grafo en tu cabeza.

**Falta de aislamiento del domain model**: las clases de dominio (AuctionSniper, SniperLauncher) se comunican directamente con el servidor XMPP y con la UI, incluso si es a través de interfaces. Introducir una header interface no equivale a adherirse al principio de inversión de dependencias.

---

## Implementacion alternativa sin mocks

La responsabilidad de AuctionSniper es simple: recibe eventos del servidor y responde con comandos, manteniendo una máquina de estados interna:

```
Auction Server --> [raw message] --> AuctionSniperViewModel
AuctionSniperViewModel --> [AuctionEvent] --> AuctionSniper
AuctionSniper --> [AuctionCommand] --> AuctionSniperViewModel
AuctionSniperViewModel --> [command string] --> Auction Server
```

El domain model esta completamente aislado. Toda la comunicacion con el exterior es manejada por `AuctionSniperViewModel`, que actua como escudo. No hay dependencias ciclicas. No hay abstracciones forzadas.

### Application Service

```python
class AuctionSniperViewModel:
    def __init__(self, item_id: str, stop_price: int, chat) -> None:
        self._sniper = AuctionSniper(item_id, stop_price)
        self._chat = chat
        self._chat.on_message_received = self._on_message_received

    def _on_message_received(self, raw_message: str) -> None:
        event = AuctionEvent.from_string(raw_message)
        command = self._sniper.process(event)
        if not command.is_none():
            self._chat.send_message(str(command))
```

Sin logica de negocio. La capa de Application Services solo orquesta, no razona.

### Domain Model en Python

```python
from dataclasses import dataclass, field
from enum import Enum, auto


class SniperState(Enum):
    JOINING  = auto()
    BIDDING  = auto()
    WINNING  = auto()
    WON      = auto()
    LOST     = auto()


@dataclass(frozen=True)
class AuctionEvent:
    type: str
    price: int = 0
    increment: int = 0
    bidder: str = ""

    @classmethod
    def price(cls, price: int, increment: int, bidder: str) -> "AuctionEvent":
        return cls(type="PRICE", price=price, increment=increment, bidder=bidder)

    @classmethod
    def close(cls) -> "AuctionEvent":
        return cls(type="CLOSE")

    def is_price(self) -> bool:
        return self.type == "PRICE"

    def is_close(self) -> bool:
        return self.type == "CLOSE"


@dataclass(frozen=True)
class AuctionCommand:
    type: str
    amount: int = 0

    @classmethod
    def bid(cls, amount: int) -> "AuctionCommand":
        return cls(type="BID", amount=amount)

    @classmethod
    def none(cls) -> "AuctionCommand":
        return cls(type="NONE")

    def is_none(self) -> bool:
        return self.type == "NONE"

    def __str__(self) -> str:
        return "NONE" if self.is_none() else f"BID {self.amount}"


NO_COMMAND = AuctionCommand.none()


@dataclass
class AuctionSniper:
    item_id: str
    stop_price: int
    state: SniperState = field(default=SniperState.JOINING, init=False)
    last_price: int = field(default=0, init=False)
    last_bid: int = field(default=0, init=False)

    SNIPER_ID = "sniper"

    def process(self, event: AuctionEvent) -> AuctionCommand:
        if event.is_price():
            return self._handle_price(event)
        if event.is_close():
            return self._handle_close()
        return NO_COMMAND

    def _handle_price(self, event: AuctionEvent) -> AuctionCommand:
        self.last_price = event.price
        if event.bidder == self.SNIPER_ID:
            self.state = SniperState.WINNING
            return NO_COMMAND
        bid = event.price + event.increment
        if bid <= self.stop_price:
            self.last_bid = bid
            self.state = SniperState.BIDDING
            return AuctionCommand.bid(bid)
        return NO_COMMAND

    def _handle_close(self) -> AuctionCommand:
        self.state = SniperState.WON if self.state == SniperState.WINNING else SniperState.LOST
        return NO_COMMAND
```

`@dataclass(frozen=True)` da inmutabilidad e igualdad por valor sin implementar `__eq__` ni `__hash__` manualmente. `Enum` con `auto()` elimina valores arbitrarios.

---

## Test suite sin mocks

Un domain model aislado se puede testear con estilo funcional: verificar la salida y el estado resultante, sin atender a como se logra ese resultado. Sin setup de mocks, sin `verify()`, sin inspeccion de estado interno por reflexion.

```python
def test_joining_sniper_loses_when_auction_closes():
    sniper = AuctionSniper("item-001", stop_price=200)

    command = sniper.process(AuctionEvent.close())

    assert command == NO_COMMAND
    assert sniper.state == SniperState.LOST
    assert sniper.last_price == 0
    assert sniper.last_bid == 0


def test_sniper_bids_when_price_from_other_bidder_arrives():
    sniper = AuctionSniper("item-001", stop_price=200)

    command = sniper.process(AuctionEvent.price(price=1, increment=2, bidder="other"))

    assert command == AuctionCommand.bid(3)
    assert sniper.state == SniperState.BIDDING
    assert sniper.last_price == 1
    assert sniper.last_bid == 3


def test_sniper_wins_when_own_bid_leads():
    sniper = AuctionSniper("item-001", stop_price=200)
    sniper.process(AuctionEvent.price(price=1, increment=2, bidder="other"))

    command = sniper.process(AuctionEvent.price(price=3, increment=2, bidder="sniper"))

    assert command == NO_COMMAND
    assert sniper.state == SniperState.WINNING


def test_sniper_does_not_bid_above_stop_price():
    sniper = AuctionSniper("item-001", stop_price=5)

    command = sniper.process(AuctionEvent.price(price=4, increment=3, bidder="other"))

    assert command == NO_COMMAND
    assert sniper.state == SniperState.JOINING
```

La comparacion `command == AuctionCommand.bid(3)` funciona por igualdad de valor gracias a `@dataclass(frozen=True)`, sin codigo extra.

El unico lugar donde los mocks estarian justificados es al testear la capa de Application Services que se comunica con sistemas externos. Pero como esa parte esta cubierta por tests end-to-end, tampoco es necesario.

---

## Conclusiones

No solo enfocarse en el patron de comunicacion entre clases individuales lleva a unit tests fragiles, sino que tambien conlleva dano arquitectonico (*test-induced design damage*).

Para evitar ese dano:

- No crear abstracciones forzadas para clases de dominio solo para poder mockearlas.
- Minimizar dependencias ciclicas.
- Aislar el domain model: las clases de dominio no se comunican con el mundo exterior.
- Aplanar la estructura de clases, reducir capas de indireccion.
- Verificar salida y estado al hacer unit testing del domain model.

El libro GOOS tiene material extremadamente valioso, especialmente en sus dos primeras secciones. La regla "only mock types that you own", el Walking Skeleton, el ciclo TDD de dos niveles, y el enfoque en testing de comportamiento son principios solidos. El problema es el enfoque en verificacion de colaboracion entre clases de dominio individuales, que genera los tres problemas descritos: header interfaces, dependencias ciclicas, y falta de aislamiento del domain model.
