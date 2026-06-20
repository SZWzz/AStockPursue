package market

import "time"

type LocalStore struct {
	basePath string
}

func NewLocalStore(basePath string) *LocalStore {
	return &LocalStore{basePath: basePath}
}

func (ls *LocalStore) SaveBars(symbol string, start, end time.Time, freq string, data []byte) error {
	return nil
}

func (ls *LocalStore) LoadBars(symbol string, start, end time.Time, freq string) ([]byte, bool) {
	return nil, false
}

func (ls *LocalStore) Path() string {
	return ls.basePath
}
