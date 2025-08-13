PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE content_type (
	pk INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	PRIMARY KEY (pk), 
	UNIQUE (name)
);
CREATE TABLE IF NOT EXISTS "key" (
	pk INTEGER NOT NULL, 
	hkid VARCHAR(34) NOT NULL, 
	hkey VARCHAR(34) NOT NULL, 
	computed BOOLEAN NOT NULL, 
	halg VARCHAR(16), 
	PRIMARY KEY (pk)
);
CREATE TABLE IF NOT EXISTS "User" (
	pk INTEGER NOT NULL, 
	username VARCHAR(32) NOT NULL, 
	password VARCHAR(512) NOT NULL, 
	must_change BOOLEAN, 
	email VARCHAR(256) NOT NULL, 
	last_login DATETIME, 
	groups_mask INTEGER NOT NULL, 
	reset_expires DATETIME, 
	reset_token VARCHAR(32), 
	PRIMARY KEY (pk), 
	UNIQUE (username), 
	UNIQUE (email)
);
INSERT INTO User VALUES(1,'admin','',1,'admin',NULL,1073741824,NULL,NULL);
CREATE TABLE IF NOT EXISTS "Blob" (
	pk INTEGER NOT NULL, 
	filename VARCHAR NOT NULL, 
	created DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	size INTEGER NOT NULL, 
	sha1_hash VARCHAR(42) NOT NULL, 
	content_type VARCHAR(64) NOT NULL, 
	auto_delete BOOLEAN NOT NULL, 
	PRIMARY KEY (pk), 
	UNIQUE (filename)
);
CREATE TABLE IF NOT EXISTS "Stream" (
	pk INTEGER NOT NULL, 
	title VARCHAR(120), 
	directory VARCHAR(32), 
	marlin_la_url VARCHAR, 
	playready_la_url VARCHAR, 
	timing_reference TEXT, 
	defaults TEXT, 
	PRIMARY KEY (pk)
);
CREATE TABLE mp_stream (
	pk INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	options TEXT, 
	PRIMARY KEY (pk)
);
CREATE TABLE media_file (
	pk INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	stream INTEGER NOT NULL, 
	blob INTEGER NOT NULL, 
	rep TEXT, 
	bitrate INTEGER NOT NULL, 
	content_type VARCHAR(64), 
	track_id INTEGER, 
	codec_fourcc VARCHAR(16), 
	encrypted BOOLEAN NOT NULL, 
	PRIMARY KEY (pk), 
	FOREIGN KEY(stream) REFERENCES "Stream" (pk), 
	UNIQUE (blob), 
	FOREIGN KEY(blob) REFERENCES "Blob" (pk)
);
CREATE TABLE IF NOT EXISTS "Token" (
	pk INTEGER NOT NULL, 
	jti VARCHAR(40) NOT NULL, 
	token_type INTEGER NOT NULL, 
	user_pk INTEGER, 
	created DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	expires DATETIME, 
	revoked BOOLEAN NOT NULL, 
	PRIMARY KEY (pk), 
	FOREIGN KEY(user_pk) REFERENCES "User" (pk)
);
CREATE TABLE period (
	pk INTEGER NOT NULL, 
	pid VARCHAR(62) NOT NULL, 
	parent_pk INTEGER NOT NULL, 
	ordering INTEGER NOT NULL, 
	stream_pk INTEGER NOT NULL, 
	start DATETIME NOT NULL, 
	duration DATETIME NOT NULL, 
	PRIMARY KEY (pk), 
	CONSTRAINT single_period_id_per_mp_stream UNIQUE (parent_pk, pid), 
	FOREIGN KEY(parent_pk) REFERENCES mp_stream (pk), 
	FOREIGN KEY(stream_pk) REFERENCES "Stream" (pk)
);
CREATE TABLE mediafile_keys (
	media_pk INTEGER NOT NULL, 
	key_pk INTEGER NOT NULL, 
	PRIMARY KEY (media_pk, key_pk), 
	FOREIGN KEY(media_pk) REFERENCES media_file (pk), 
	FOREIGN KEY(key_pk) REFERENCES "key" (pk)
);
CREATE TABLE media_file_error (
	pk INTEGER NOT NULL, 
	reason INTEGER NOT NULL, 
	details VARCHAR(200) NOT NULL, 
	media_pk INTEGER NOT NULL, 
	PRIMARY KEY (pk), 
	CONSTRAINT single_reason_per_file UNIQUE (reason, media_pk), 
	FOREIGN KEY(media_pk) REFERENCES media_file (pk)
);
CREATE TABLE adaptation_set (
	pk INTEGER NOT NULL, 
	period_pk INTEGER NOT NULL, 
	track_id INTEGER NOT NULL, 
	role INTEGER NOT NULL, 
	content_type_pk INTEGER NOT NULL, 
	encrypted BOOLEAN NOT NULL, 
	lang VARCHAR(16), 
	PRIMARY KEY (pk), 
	CONSTRAINT single_track_id_per_period UNIQUE (period_pk, track_id), 
	FOREIGN KEY(period_pk) REFERENCES period (pk), 
	FOREIGN KEY(content_type_pk) REFERENCES content_type (pk)
);
CREATE UNIQUE INDEX ix_key_hkid ON "key" (hkid);
CREATE UNIQUE INDEX "ix_Stream_directory" ON "Stream" (directory);
CREATE UNIQUE INDEX ix_mp_stream_name ON mp_stream (name);
CREATE INDEX ix_media_file_track_id ON media_file (track_id);
CREATE UNIQUE INDEX ix_media_file_name ON media_file (name);
CREATE INDEX ix_media_file_content_type ON media_file (content_type);
CREATE INDEX ix_media_file_encrypted ON media_file (encrypted);
CREATE INDEX ix_media_file_bitrate ON media_file (bitrate);
COMMIT;
