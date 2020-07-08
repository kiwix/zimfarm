from marshmallow import fields, validate

from common.schemas import SerializableSchema, StringEnum
from common.schemas.fields import validate_output


class OpenedxFlagsSchema(SerializableSchema):
    class Meta:
        ordered = True

    course_url = fields.Url(
        metadata={
            "label": "Course URL",
            "description": "URL of the course you wnat to scrape",
        },
        data_key="course-url",
        required=True,
    )

    email = fields.String(
        metadata={
            "label": "Registered e-mail",
            "description": "The registered e-mail ID on the openedx instance",
        },
        data_key="email",
        required=True,
    )

    password = fields.String(
        metadata={
            "label": "Password",
            "description": "Password to the account registered on the openedx instance",
            "secret": True,
        },
        data_key="password",
        required=True,
    )

    ignore_missing_xblocks = fields.Boolean(
        truthy=[True],
        falsy=[False],
        metadata={
            "label": "Ignore unsupported xblocks",
            "description": "Ignore unsupported content (xblock(s))",
        },
        data_key="ignore-missing-xblocks",
    )

    add_wiki = fields.Boolean(
        truthy=[True],
        falsy=[False],
        metadata={
            "label": "Include wiki",
            "description": "Add wiki (if available) to the ZIM",
        },
        data_key="add-wiki",
    )

    add_forum = fields.Boolean(
        truthy=[True],
        falsy=[False],
        metadata={
            "label": "Include forum",
            "description": "Add forum/discussion (if available) to the ZIM",
        },
        data_key="add-forum",
    )

    video_format = StringEnum(
        metadata={
            "label": "Video format",
            "description": "Format to download/transcode video to. webm is smaller",
        },
        validate=validate.OneOf(["webm", "mp4"]),
        data_key="format",
    )

    low_quality = fields.Boolean(
        truthy=[True],
        falsy=[False],
        metadata={
            "label": "Low Quality",
            "description": "Re-encode video using stronger compression",
        },
        data_key="low-quality",
    )

    name = fields.String(
        metadata={
            "label": "Name",
            "description": "ZIM name. Used as identifier and filename (date will be appended)",
            "placeholder": "topic_eng",
        },
        data_key="name",
        required=True,
    )

    title = fields.String(
        metadata={
            "label": "Title",
            "description": "Custom title for your ZIM. Based on MOOC otherwise",
        },
        data_key="title",
    )

    description = fields.String(
        metadata={
            "label": "Description",
            "description": "Custom description for your ZIM. Based on MOOC otherwise",
        },
        data_key="description",
    )

    creator = fields.String(
        metadata={
            "label": "Content Creator",
            "description": "Name of content creator. Defaults to edX",
        },
        data_key="creator",
    )

    tags = fields.String(
        metadata={
            "label": "ZIM Tags",
            "description": "List of comma-separated Tags for the ZIM file. category:openedx, and openedx added automatically",
        },
        data_key="tags",
    )

    optimization_cache = fields.Url(
        metadata={
            "label": "Optimization Cache URL",
            "description": "URL with credentials and bucket name to S3 Optimization Cache",
            "secret": True,
        },
        data_key="optimization-cache",
    )

    use_any_optimized_version = fields.Boolean(
        truthy=[True],
        falsy=[False],
        metadata={
            "label": "Use any optimized version",
            "description": "Use the cached files if present, whatever the version",
        },
        data_key="use-any-optimized-version",
    )

    output = fields.String(
        metadata={
            "label": "Output folder",
            "placeholder": "/output",
            "description": "Output folder for ZIM file(s). Leave it as `/output`",
        },
        missing="/output",
        default="/output",
        validate=validate_output,
        data_key="output",
    )

    tmp_dir = fields.String(
        metadata={
            "label": "Temp folder",
            "description": "Where to create temporay build folder. Leave it as `/output`",
        },
        missing="/output",
        default="/output",
        validate=validate_output,
        data_key="tmp-dir",
    )

    zim_file = fields.String(
        metadata={
            "label": "ZIM filename",
            "description": "ZIM file name (based on ZIM name if not provided)",
        },
        data_key="zim-file",
    )

    debug = fields.Boolean(
        truthy=[True],
        falsy=[False],
        metadata={"label": "Debug", "description": "Enable verbose output"},
    )
