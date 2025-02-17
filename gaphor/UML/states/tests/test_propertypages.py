from gaphor import UML
from gaphor.diagram.tests.fixtures import find
from gaphor.UML.states.propertypages import StatePropertyPage, TransitionPropertyPage


def test_state_property_page_entry(element_factory):
    subject = element_factory.create(UML.State)
    property_page = StatePropertyPage(subject)

    widget = property_page.construct()
    entry = find(widget, "entry")
    entry.set_text("test")

    assert subject.entry.name == "test"


def test_state_property_page_exit(element_factory):
    subject = element_factory.create(UML.State)
    property_page = StatePropertyPage(subject)

    widget = property_page.construct()
    exit = find(widget, "exit")
    exit.set_text("test")

    assert subject.exit.name == "test"


def test_state_property_page_do_activity(element_factory):
    subject = element_factory.create(UML.State)
    property_page = StatePropertyPage(subject)

    widget = property_page.construct()
    do_activity = find(widget, "do-activity")
    do_activity.set_text("test")

    assert subject.doActivity.name == "test"


def test_transition_property_page(element_factory):
    subject = element_factory.create(UML.Transition)
    property_page = TransitionPropertyPage(subject)

    widget = property_page.construct()
    guard = find(widget, "guard")
    guard.set_text("test")

    assert subject.guard.specification == "test"
