PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
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
CREATE TABLE IF NOT EXISTS "key" (
	pk INTEGER NOT NULL,
	hkid VARCHAR(34) NOT NULL,
	hkey VARCHAR(34) NOT NULL,
	computed BOOLEAN NOT NULL,
	halg VARCHAR(16),
	PRIMARY KEY (pk)
);
CREATE TABLE IF NOT EXISTS "Stream" (
	pk INTEGER NOT NULL,
	title VARCHAR(120),
	directory VARCHAR(32),
	marlin_la_url VARCHAR,
	playready_la_url VARCHAR,
	timing_reference TEXT,
	PRIMARY KEY (pk)
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
CREATE TABLE media_file (
	pk INTEGER NOT NULL,
	name VARCHAR(200) NOT NULL,
	stream INTEGER NOT NULL,
	blob INTEGER NOT NULL,
	rep TEXT,
	bitrate INTEGER NOT NULL,
	content_type VARCHAR(64),
	encrypted BOOLEAN NOT NULL,
	PRIMARY KEY (pk),
	FOREIGN KEY(stream) REFERENCES "Stream" (pk),
	UNIQUE (blob),
	FOREIGN KEY(blob) REFERENCES "Blob" (pk)
);
CREATE TABLE mediafile_keys (
	media_pk INTEGER NOT NULL,
	key_pk INTEGER NOT NULL,
	PRIMARY KEY (media_pk, key_pk),
	FOREIGN KEY(media_pk) REFERENCES media_file (pk),
	FOREIGN KEY(key_pk) REFERENCES "key" (pk)
);
CREATE UNIQUE INDEX ix_key_hkid ON "key" (hkid);
CREATE UNIQUE INDEX "ix_Stream_directory" ON "Stream" (directory);
CREATE UNIQUE INDEX ix_media_file_name ON media_file (name);
CREATE INDEX ix_media_file_content_type ON media_file (content_type);
CREATE INDEX ix_media_file_bitrate ON media_file (bitrate);
CREATE INDEX ix_media_file_encrypted ON media_file (encrypted);
COMMIT;

