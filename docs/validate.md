# DASH Stream Validation

## Introduction

The [/validate](http://localhost:5000/validate/) page allows the checking
the validity of a DASH stream. It will inspect the contents of the DASH
manifest and all the requested segments in the stream. If it finds
any values that don't adhere to the DASH specification, they will be
logged in the output summary.

## Options

### Generic Options

The `Manifest to check` input field is use to provide the HTTP URL of the
DASH manifest.

The `Maximum duration` input field is used to control how many seconds of
the DASH stream will be checked. If this value is larger than
`MPD@availabilityStartTime`, the validator will have to pause one or
more times to wait until new fragments become available from the stream's
origin.

The validator needs to know if the stream is encrypted, so that it can
perform additional checks. The `Stream is encrypted?` checkbox needs to
match the setting of the stream being validated.

The `Check media segments` option controls if the validator should just
check the manifest and init segments, or also check media segments.
Turning off the `Check media segments` option will speed up validation.

The `Verbose output` can be used to turn on the debug logging in the
validator. Sometimes this is useful to learn more information about the
stream or when investigating bugs in the validator.

When the `Pretty print XML before validation` option is enabled, an
XML "pretty print" will be applied to the XML manifest before it is
validated. This can be useful to make it easier to read the manifest.
For each error discovered in the stream, the line in the manifest
associated with this validation error will be highlighted. A pretty
printed version of the manifest might make that highlighting easier
to read.

When the `Add stream to this server` option is enabled, in addition to
validating the stream, it will be added as a new stream on this server.
Every `Representation` in the manifest will be used to create an
individual media file. Once validation has completed, a new playable
stream should have been added to the server.

### Stream Saving Options

The `Destination directory` option is used to set the directory that is
used to store the downloaded media files and also as the `directory`
setting in the stream that will be created.

The `Stream title` option is used to set the `title` property in the
stream that will be created.

## Implementation Details

The validator uses multiple threads to fetch and validate each segment
of a DASH stream. If the `Add stream to this server` checkbox has been
selected, the same pool of threads is used to save media data files.

The validator was originally developed for unit testing the server. It
is not meant to be a complete DASH validation tool. It is highly likely
that many streams will fail to parse and trigger bugs in the validator.
