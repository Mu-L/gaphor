from __future__ import annotations

import functools
import logging
from pathlib import Path

import sphinx.util.docutils
from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.directives import images
from sphinx.util.console import bold, darkred, red

from gaphor.core.eventmanager import EventManager
from gaphor.core.modeling import Diagram, ElementFactory
from gaphor.i18n import gettext
from gaphor.plugins.diagramexport import DiagramExport
from gaphor.services.modelinglanguage import ModelingLanguageService
from gaphor.storage import storage

# TODO: How to know a model has changed and we should regenerate images?
# TODO: test with PDF output
# TODO: Add warning/note blocks when diagram render fails
# TODO: Add Diagram.qualifiedName

log = logging.getLogger(__name__)


def setup(app: sphinx.application.Sphinx) -> dict[str, object]:
    """Called by Sphinx to set up the extension."""
    app.add_config_value("gaphor_models", {}, "env", [dict])

    app.add_directive("diagram", DiagramDirective)

    app.connect("config-inited", config_inited)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


def config_inited(app, config):
    log.info(f"Gaphor models: {config.gaphor_models}")
    if isinstance(config.gaphor_models, str):
        config.gaphor_models = {"default": config.gaphor_models}


class DiagramDirective(sphinx.util.docutils.SphinxDirective):
    """The Gaphor diagram directive.

    Usage: "``.. diagram:: diagram-name``".
    """

    has_content = False
    required_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "model": directives.unchanged,
        "alt": directives.unchanged,
        "height": directives.length_or_unitless,
        "width": directives.length_or_percentage_or_unitless,
        "align": images.Image.align,
        "scale": directives.percentage,
        "target": directives.unchanged_required,
        "class": directives.class_option,
        "name": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        name = self.arguments[0]
        model_name = self.options.get("model", "default")
        model_file = self.config.gaphor_models.get(model_name)

        if not model_file:
            text = gettext("No model file configured for model '{model_name}'.").format(
                model_name=model_name
            )
            log.error(darkred(bold(gettext("Gaphor diagram: "))) + red(text))
            return [
                nodes.error("", nodes.paragraph(text=text), title="Gaphor model error")
            ]

        model = load_model(model_file)
        outdir = Path(self.env.app.doctreedir).relative_to(Path.cwd()) / ".." / "gaphor"
        outdir.mkdir(exist_ok=True)
        self.state.document.settings.record_dependencies.add(model_file)

        diagram = next(
            model.select(lambda e: isinstance(e, Diagram) and qualifiedName(e) == name),
            None,
        )

        if not diagram:
            diagram = next(
                model.select(lambda e: isinstance(e, Diagram) and e.name == name), None
            )

        if not diagram:
            text = gettext(
                "No diagram '{name}' in model '{model_name}' ({model_file})."
            ).format(name=name, model_name=model_name, model_file=model_file)
            log.error(darkred(bold(gettext("Gaphor diagram: "))) + red(text))
            return [nodes.error("", nodes.paragraph(text=text))]

        outfile = outdir / f"{diagram.id}.svg"
        DiagramExport().save_svg(outfile, diagram)

        return [
            nodes.image(
                rawsource=self.block_text,
                uri=str(outfile),
                **self.options,
            ),
        ]


@functools.lru_cache(maxsize=None)
def load_model(model_file: str) -> ElementFactory:
    element_factory = ElementFactory()
    storage.load(
        model_file,
        element_factory,
        modeling_language=ModelingLanguageService(EventManager()),
    )
    return element_factory


def qualifiedName(diagram: Diagram) -> str:
    """Returns the qualified name of the element as a tuple."""
    if diagram.owner:
        return f"{qualifiedName(diagram.owner)}.{diagram.name}"  # type: ignore[arg-type]
    else:
        return diagram.name  # type: ignore[no-any-return]
